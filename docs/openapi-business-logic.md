# 顺店通开放接口 · 代码业务逻辑梳理

> 用途：客户对接开放接口时，回答「这个接口到底做了什么、什么情况会失败、为什么没收到推送」。
> 文档清单见 `docs/openapi-inventory.md`，错误码见 `docs/openapi-error-codes.md`。
> 代码基线：`eps-store-core-united-store-be`，行号以 `feature/uat-branch-202608` 检出为准（该分支已合入 `feature/v3.68.5`）。
> 路径简写：`OS` = `united-store-open-server/.../openserver`，`MG` = `united-store-manager/.../manager`，`MQ` = `united-store-mq-consumer/.../consumer`。
> 两个服务 context-path 均为 `/api`，故文档路径 `/api/xxx` 与 `@RequestMapping("/xxx")` 叠加后一致。

---

## 1. 通用鉴权（所有接口共用，先读这节）

### 1.1 三种校验入口

| 方法 | 位置 | 校验内容 | 凭证表 |
|---|---|---|---|
| `checkSign` | `OS/controller/AbstractController.java:34` | appId 转 Long → 组织存在（`queryEastOrgByIdCache`）→ `us_open_config` 有记录 → 验签 | `us_open_config` |
| `checkSignNoOrg` | `:55` | 跳过组织存在性校验，只查 `us_open_config` + 验签 | 同上 |
| `checkOpenicSign` | `:64` | 同 `checkSign`，入参为 `OpenicRequestBaseInfo`（仅 4 字段），同城 `/tc` 专用 | 同上 |

> `checkSignNoOrg` 实际无人启用（仅 `YuntaController` 注释处出现）。

### 1.2 签名与时间窗（`OS/util/CheckParamUtil.java`、`common/utils/SignUtil.java`）

1. 四参数非空：`appId` / `requestId` / `timestamp` / `sign`，缺任一报 `US_100003`「appId or requestId or timestamp or sign is empty」。
2. `timestamp` 长度必须 **10 或 13 位**；10 位按秒处理。
3. 与服务器时间差超过 **±900000ms（15 分钟）** 报「request timestamp timeout 15 minutes」。
4. 签名：`MD5_32_lower( sortAsc([appId, requestId, timestamp, appSecret]) 直接拼接 )`。
5. **业务字段与 URI 不参与签名**；`appSecret` 不出现在报文。
6. 验签失败抛 `ILLEGAL_REQUEST`，与 `PARMAS_HAS_ERROR` **同为 `US_100003`**，客户无法从 code 区分，只能看 message。

### 1.3 边界与坑

- `checkSign` **只校验 appId 是否为合法组织 + 签名是否正确，不校验 appId 与报文中店铺/运单的归属关系**。归属校验散落在各 Service，所以「签名过但查不到单」是常见组合。
- 全局异常由 `OS/aspect/GlobalExceptionAdvice.java:117` 转 HTTP 500 + `R.error(errorCode, message)`。客户侧看到 500 不一定是系统故障，多为业务校验失败。
- 组织侧另有一套顺丰凭证：`us_order.client_code / check_word` 对应组织的 `customerCode / checkCode`，用于调丰桥 BSP。**组织没配这两个值，绝大多数下单/查询接口会直接报错。**

---

## 2. 下单类（11 个）

### 2.1 总览

| # | 接口 | Controller:行 | Service:行 | 鉴权 |
|---|---|---|---|---|
| 1 | `/universal/createOrder` | `UniversalCreateOrderController.java:134` | `UniversalCreateOrderServiceImpl.java:298`（source=1） | checkSign |
| 2 | `/universal/electric/createOrder` | 同文件 `:194` | 同上（SF source=2）/ `createThirdMonthlyOrder:1292`（三方） | checkSign |
| 3 | `/universal/electric/createOrderV2` | 同文件 `:228` | 同上 + `mergeOrderAuto:2836` | checkSign |
| 4 | `/universal/createOrderXns` | 同文件 `:159` | 同 1 + `saveHennessyOrderMapping:1269` | checkSign |
| 5 | `/preorder/times` | `PreOrderController.java:38` | `PreOrderServiceImpl.java:41` | checkOpenicSign |
| 6 | `/cancel/confirm` | `BspOrderConfirmController.java:69` | `OpenOrderTransactionalServiceImpl.java:96` | checkSign |
| 7 | `/open/subWaybillNumber/apply` | `BspCreateOrderController.java:88` | `OrderZDServiceImpl.java:88` | checkSign |
| 8 | `/cancel/order` | `BspOrderConfirmController.java:43` | `OrderConfirmServiceImpl.java:89` | checkSign |
| 9 | `/cancel/orderV2` | `:56` | `OrderConfirmServiceImpl.java:150` | checkSign |
| 10 | `/delivery/trigger` | `BspDeliverNoticeController.java:42` | `OpenBspDeliveryNoticeServiceImpl.java:36` | checkSign |
| 11 | 国补订单信息推送（出口） | `MG/controller/BspOrderBatchController.java:976` | `BspOrderBatchServiceImpl.java:7954` | **代码未见验签** |

### 2.2 统一下单 `/universal/createOrder`（标准，仅顺丰）

**DTO**：`UniversalCreateOrderReq`。关键字段 `orderNumber`（客户订单号）、`costType`、`senderOrgCode`、`payMethod`（1 寄付 / 2 到付 / 3 三方 / 4 寄付现结）、`expressType`、`parcelQuantity`、`boxNo`、`sendStartTime`、`needReturnTrackingNumber`、`cargo`、`addedService`、`otherInfoList`（国补走这里）、`crossBorderFlag`、`monthlyCustomerId`。

**执行顺序（决定成败的关键）**：

1. `checkParam`：成本类型/寄件组织/付款方式/产品/回单类型必填；产品命中失效列表直接拒；件数默认 1 上限 300；物品 ≤300 条；箱号与件数必须一致；月结卡号必须在白名单；`monthlyCustomerId` 仅允许到付；区域城配(331) 只允许保价/代收且禁签回单、微派、微签；国补单强制一票一件且必须传 wpMerchantCode / wpServiceCode。
2. 寄件组织必须属于该 `appId` 一级组织，否则「寄件组织不存在」。
3. 运费额度管控：命中 `us_freight_budget_limit` 后按三种策略处理 —— 需审批 / 自动转寄付现结 / 直接拒绝（返回 `isBudget=true`，**不落单**）。
4. 幂等：**仅当 appId 在 `idempotent.organizationIds` 白名单且传了 orderNumber** 时生效，key = 客户订单号 + 寄件组织。命中会复用历史订单号但仍重新向丰桥下单 → **不是严格幂等**。
5. 重复单校验：开关 `app.default.dulpCreateCheckFlag` 打开时，近 180 天同客户订单号直接拒。
6. **先落库**：写 `us_order`（`order_source=4` 开放平台、`order_status=0` 已导入）。
7. 调丰桥 `createOrderToBsp` → `BspOrderCreateService`；传了 `sendStartTime` 时走预约取件校验；丰桥返回「非营业时间」且配置了改约小时数会自动改约重试一次。
8. 回写：`order_status=1` 未收件、主/子运单号、`us_sub_mail`、箱号映射、`us_order_extra`、`us_mail`。
9. MQ：`HD_UNITED_STORE_CREATE_ORDER_GIS`（GIS 解析）、`HD_UNITED_STORE_ORDER_FLOW`（CREATED）；按开关发智慧快递助手、微派 OMS、面单 PDF 推送（延迟 10s）。OT/轩尼诗客户跳过这三条异步。

**重要副作用**：落库先于调丰桥，丰桥失败时订单仍停留在「已导入(0)」，**不会自动删除**，需要客户走取消或人工处理。

### 2.3 `electric/createOrder` 与 `electric/createOrderV2`（店配）

- **V1**：`shipperCode` 为空默认 `SF`。非 SF 走 `createThirdMonthlyOrder` —— 校验物流编码、收寄地址、物品名，付款方式 1 会被改写成 3（快递鸟寄付月结编码），配置取 `us_kdn_third_logistics_config`，无配置报 `US_1100015`。顺丰分支不判调度规则、不判自动合单、不校验区域城配。**代码构造了 `ElectricOrderResponse` 但没回吐 shipperCode**（未完成实现）。
- **V2**：在 V1 基础上多四件事 —— ① 调度规则命中后用规则里的物流公司和产品**覆盖入参**；② 自动合单（mergeType 0 收寄组织相同 / 1 寄件组织+收件人相同 / 2 相同订单号），命中转追加子单；③ 区域城配与 SOP 标签校验；④ 成功后写 `us_electric_order` 临时表（供后续面单路由查询）。
- **V2 的合单坑**：箱号重复且开启重试时返回历史单，message 带「箱号 xx 重复下单，返回上一次运单号」；正常合单 message 带「满足自动合单规则，进行追加子单操作」。

### 2.4 `createOrderXns`（轩尼诗）

= 标准下单 + 成功后写 `us_hennessy_order_mapping`（运单号 / 客户订单号 / 提货单 URL）。**映射写入失败只打日志不回滚**，下单本身照常成功。命中 `ot.hennessyAppIds` 时改走专用下单地址并跳过微派/微签/面单异步推送。

### 2.5 `/preorder/times`（顺丰预下单取件时间）

**只查时间，不下单**：返回可选取件日期与时间段（`serviceDate` / `startTime` / `endTime`），不占运单号、不落库、不发 MQ。

- DTO：`orderId`、`cargoName`、`monthlyCard`、`expressTypeId`、`contactInfoList`。
- 下游：顺丰标准服务 `EXP_RECE_PRE_ORDER`，form-urlencoded，`partnerID + msgDigest(MD5(json+timestamp+md5key))`。
- 鉴权特殊：走 `checkOpenicSign` 而非 `checkSign`。
- 失败码（顺丰透传）：`S0002` 参数错 / `S0008` 地址不可达 / `S0003` 系统异常，HTTP 状态 417。

### 2.6 `/cancel/confirm`（顺丰订单确认）

- DTO：`ConfirmInfoReq`，`orderNumber` / `mailNumber` 二选一（只传运单号时代码反查客户订单号）、`weight`、`childrenNumbers`、`isConfirmNew`（1 改联系人 / 2 改其他客户订单）、`checkMonthlyCard`、`extraInfoList`。
- **顺店通侧不校验订单状态**：`confirmCheck:428` 是无调用方的死代码，能否确认由丰桥判定。
- 国补单（`extraInfoList` 含 subsidySource）必须带 wpMerchantCode / wpServiceCode；只传运单号且订单状态 >3 时报「国补订单只能在派件前修改订单」。
- 结果 `resStatus != 2` 统一抛 `US_200004`「bsp订单确认返回不成功」。
- 落库：仅 `us_open_request_log`。

### 2.7 `/open/subWaybillNumber/apply`（子单号申请）

**前置条件（最常踩）**：

1. 组织必须已配置 customerCode / checkCode。
2. **母单有箱号 → 子单必须传箱号；母单无箱号 → 子单不允许传箱号**。
3. 箱号 ≤1000、长度 1–50、不重复、**数量必须等于新申请件数（1–20）**。
4. 箱号全局唯一性窗口 `getBoxNoCheckDaysIfOpen`：>0 限天数、=0 全量校验、<0 跳过；命中已用箱号报「子单申请中有箱号已被使用」。

- 落库：`us_order.parcel_quantity` 累加、`mailno` 累加子单号、`us_sub_mail`、箱号映射。
- 失败：`US_1000001` 子单号申请失败，透传丰桥原始描述（8018 订单不存在、8028 未配置业务）。

### 2.8 `/cancel/order`（V1）与 `/cancel/orderV2`

**V1 状态机（严格）**：

| 条件 | 错误码 | 文案 |
|---|---|---|
| `order_status` 为空或 ≥2（已取件） | `US_200002` | 非待收件状态不能取消订单 |
| `order_status=6` 且 abnormal_reason=「客户已取消寄件」 | `US_200020` | 此单已取消，不可重复取消 |
| `one_org_id != appId` | `US_200003` | 只能操作本门店订单 |
| `order_source != 4` | `US_200010` | 只能取消开放平台创建的订单 |

**执行顺序有坑**：**先在顺店通软删订单**（`status=2`，同步删 ES 和子运单）→ **再调丰桥取消**。若丰桥失败抛 `US_200004`，但本地订单已是删除状态（`@Transactional` 被注释，无回滚）。**客户重试会得到「订单不存在」。**

**V2 差异**：`channel == THIRD_DIRECT`（三方直连月结）时改走三方公司取消接口（德邦/韵达等），不再调丰桥；韵达超过 30 天不允许取消。其余渠道与 V1 相同。

**一句话**：三方直连单必须用 V2，用 V1 会当丰桥单取消而失败。

### 2.9 `/delivery/trigger`（放行 / 退回）

- `dataType`：**71 = 派送通知（放行）**、**72 = 通知退回**。
- 纯转发丰桥，无本地落库、无 MQ、无状态留存；重复发起以丰桥返回为准。
- 失败：`BSP_OPERATION_FAILED` 透传丰桥原始描述。

### 2.10 国补订单信息推送（顺店通 → 客户）

- 入口在 manager 模块 `/api/order/batch/countrySubsidyPush`，**代码未见任何验签**（`BspBaseRequest` 的 msgDigest/nonce/timestamp 未读取校验）。
- 处理链：运单号为空 → 查 ES 无单 → 客户地址配置 `us_customer_address_config`（需 url + secret_key）缺失 → `photoUrl` 用该客户 **secretKey 做 AES256 解密**（16 字节全 0 IV）→ POST JSON 到客户 url。
- 响应 `CountrySubsidyInfoBspVO{success, retryFlag, errorCode, errorMsg}`；`retryFlag` 恒等于 `success`。
- 触发条件：代码内无定时任务、无 MQ 消费入口，**仅由顺丰/BSP 主动回调**；具体在签收还是派件时触发需与丰桥侧确认。

---

## 3. 查询类（8 个）

| # | 接口 | Controller:行 | Service:行 |
|---|---|---|---|
| 12 | `/order/deliverTm` | `BspOrderSearchController.java:184` | `DeliverTmServiceImpl.java:54` |
| 13 | `/wayBillNo/validate` | `BspValidateWayBillNoController.java:38` | `BspValidateWayBillNoServiceImpl.java:52` |
| 14 | `/order/freight` | `BspOrderSearchController.java:104` | `OrderFreightServiceImpl.java:76` |
| 15 | `/gis/adsp/addressIdentify` | `GisController.java:73` | `CommonGisServiceImpl.java:139` |
| 16 | `/order/allChannelSearch` | `BspOrderSearchController.java:220` | 复用 `OrderSearchServiceImpl.java:61` |
| 17 | `/order/search` | `:78` | `OrderSearchServiceImpl.java:61` |
| 18 | `/order/schedule` | `:196` | `OrderScheduleServiceImpl.java:50` |
| 19 | `/openNuts/monthly/queryMonthlyWaybill` | `MonthlyCodeController.java:39` | `MonthlyCodeServiceImpl.java:191` |

### 3.1 时效查询 `/order/deliverTm`

- **计算口径：完全调丰桥算时效与运费，本地无任何费率表**。
- 先调 GIS 解析寄/收地址 → 组 `BspDeliverTmRequest`（`searchPrice="1"`，未传 consignedTime 取当前时间）→ 调丰桥 `DeliverTmService`。
- 产品匹配降级链：指定 `expressType` 精确匹配 → 未命中降级标准快递 `"1"` → 再降级取第一条；未传则直接取第一条。
- 失败：组织无 customerCode/checkCode → 参数异常；丰桥 `head=ERR` → `ROUTE_QUERY_ERROR`(`US_800002`)；响应为空返回 `null`（**是成功响应里的空，不是报错**）。

### 3.2 运单号校验 `/wayBillNo/validate`

- **纯透传，不查顺店通库**：调丰桥 `EXP_RECE_VALIDATE_WAYBILLNO`，格式与可达性全由丰桥判定。
- 错误码（丰桥）：`S0000` 成功 / `S0002` 参数错误 / `S0008` 地址不可达 / `S0003` 系统异常。
- 隐患：Service 返回 null 时 Controller 会 NPE。

### 3.3 清单运费查询 `/order/freight`

- 入参三种组合决定查询类型：有订单号 → type=1；只有运单号且无 phone → 先查 ES 换订单号；运单号 + phone → type=2 按运单号 + 电话尾号查。
- **调丰桥实时查，本地无费率来源表**。失败 → `QUERY_ORDER_FREIGHT_ERROR`(`US_200012`)。
- 注意：全渠道运费（`allChannelFreight`）**不走丰桥**，读 `us_bill_detail` + `us_bill_fee_detail`，与这个接口不是同一份数据。

### 3.4 地址解析 `/gis/adsp/addressIdentify`

**三道闸，任一不过都拿不到结果**：

1. `appId` 必须在 nacos `gis.appids` 白名单，否则「此 appid 不允许访问 gis」。
2. `addressList` 单次 **≤50 条**。
3. 限流：**200 次/秒、500000 次/天，且按条计数** —— 一次传 50 条会消耗 50 次配额。

- 解析失败**不抛错**：返回 `status=1` + 「地址填写不规范，请重新正确填写！」+ 原地址回显。客户看到这条要当作「解析不了」而非接口故障。

### 3.5 下单结果查询 `/order/search` 与 `/order/allChannelSearch`

- `orderNumber` / `mailNumber` 至少一个；订单号为空则用运单号查 ES 换客户订单号。
- 流程：调丰桥 → 用返回的首个运单号查 ES 补状态 → 组合返回。
- **文档标「付费」但代码未见扣费**：`allChannelSearch` 无服务开通校验、无扣费、无流水（对照路由 v2 才有）。接入前需与商务确认计费口径。
- 错误码复用不当：查询异常统一包成 `US_200004`（`CANAL_ORDER_ORDER`，语义是「取消订单失败」）。**客户看到「取消订单失败」实际是查询异常**。

### 3.6 调度信息 `/order/schedule`

- `orders + mailnos` 总数 **>20 条直接拒**（`US_300003`）。
- 只读 `us_push_order_state`（ES），不调外部、不落库。空结果返回空数组。

### 3.7 月结付款码查单 `/openNuts/monthly/queryMonthlyWaybill`

- 入参 `uuid`（月结码生成的 uuid）+ `monthlyCard`；组织存在且 `enable != 0`。
- 查 `us_monthly_billing_waybill`（status=1 + uuid + `monthly_card = SM2加密(monthlyCard)` + 组织路径），**固定最多 1000 条，无分页参数**。
- 每条运单再查顺丰运单安全接口取手机号后 4 位；取不到则 `contact` 为空。

---

## 4. 路由类（5 个）

| # | 接口 | Controller:行 | Service:行 |
|---|---|---|---|
| 20 | `/order/routeQuery` | `BspOrderSearchController.java:116` | `OrderRouteServiceImpl.java:89`（checkIfBelongToSDT=true） |
| 21 | `/order/routeQuery/v2` | `:128` | 同上（false） |
| 22 | `/order/allChannelRouteQuery` | `:143` | `OrderRouteServiceImpl.java:122` |
| 23 | `/order/allChannelRouteQuery/v2` | `:159` | `AllChannelRouteQueryNewServiceImpl.java:87` |
| 24 | 标准路由推送（出口） | 不在 `RouteController` | 见 4.3 |

### 4.1 `routeQuery` vs `routeQuery/v2`（**v2 是新版**）

| 差异 | v1 | v2 |
|---|---|---|
| 归属校验 | 本地查 ES 校验 appId 归属；特殊组织 547810/492092 可跨查 | 不查本地订单，直接透传丰桥 |
| `phone` | 不要求 | **必填** |
| `tracking_type` | 固定 2（按客户订单号） | 有订单号 → 2；只有运单号 → 1 |
| 超期 | 下单超 **90 天**报 `ROUTE_TIME_OUT`(`US_800001`) | 无此限制 |
| CX 兼容 | 否 | **是** |

共同点：组织须配 customerCode/checkCode；运单/订单号至少一个。失败统一 `ROUTE_QUERY_ERROR`(`US_800002`)。

### 4.2 `allChannelRouteQuery` vs `/v2`（**v2 是新版且付费**）

| 差异 | v1 | v2 |
|---|---|---|
| 服务开通 | 无 | 校验 `us_service_open` 类型 12「预充值账户」enable=1，否则 `NOT_AVAILABLE`(`US_101009`) |
| 去重 | 无 | Redis 单号锁 + 查 `us_amt_account_flow_record` |
| 扣费 | 无 | 余额锁 → 校验余额 ≥ 每单费 → **查询成功才扣费** + 写流水 |
| 落库 | 无 | 每次写 `us_route_query_record` |
| 重复查询 | — | 同单号再查免费（isDuplicate=1）直接返回 |

失败：余额不足/未充值 → `US_100002`；锁抢占失败 → `US_100001`。

### 4.3 标准路由推送（顺店通 → 客户）

**两条链路并存**，注意区分：

1. **路由推送**：顺丰 BSP 回调 → `HD_UNITED_STORE_ROUTE_DISTRIBUTE_TOPIC` → `RouteDistributePushServiceImpl.distributePush:54` → 读 `us_route_push_config`（pushUrl / appId / appSecret / productId / pushType）→ 按 pushType 选策略（COMMON / COMMON_ENCRYPT_INFO / ZHESHANG_BANK / SYT）→ POST 到客户。
2. **运单信息推送**：`HD_UNITED_STORE_FULL_CHANNEL_ROUTE_PUSH`，推的是重量/体积/揽收签收时间，**和路由推送不是一个出口**。

- 加签：`[appId, appSecret, productId, id, mailNumber, orderNumber, timestamp]` 排序拼接 MD5，头字段带 appId / productId / timestamp / sign。
- 标准状态码 `FullChannelRoutePushEnum`：100 未收件 / 110 已收件 / 120 运输中 / 130 派件中 / 200 已签收 / 300 异常件 / 900 已取消 —— **推给客户的是标准码，不是顺丰原始 opCode**。
- 未配置 `us_route_push_config` 则不推。

---

## 5. 打印类（1 个）

### 5.1 云打印 `/fq/cloundPrint`

- Controller `FengmenController.java:27` → `CloundPrintServiceImpl.java:29` → `FQCommonServiceImpl.java:35`。
- DTO：`templateCode`（1–3，1 = `fm_76130_standard`、2 = `fm_150_standard`、3 = `fm_210_standard`）、`masterWaybillNo`、`branchWaybillNos`（逗号分隔）、`backWaybillNo`（签回单）、`recTelSuffix` / `sendTelSuffix`、`isPrintLogo`、`extJson{channel, encryptFlag, mergePdf, mergeType}`。
- 一次请求合并返回：母单(seq=1) + 签回单 + 各子单，`sum` = 单据总数；调丰桥云打印，header 带 `sysCode/reqTime/signature`。
- **响应 `obj.files[]` 的 url 是已编码的 PDF 下载地址（GET）**，下载需带 header `X-Auth-token` = 对应 token；代码注释标注 **token 有效期 24 小时**；**files 不保证顺序，必须按 `seqNo` 排序**。
- 失败：丰桥异常 → `GENERAT_PDF_ERROR`(`US_100047`)；模板编码越界/主单号空 → 参数校验。

---

## 6. O2O 类（9 个）

入口 `OtoOpenController.java`，实现 `OtoOpenServiceImpl.java`（2008 行）。

| # | 接口 | Controller:行 | Service:行 | 请求 DTO |
|---|---|---|---|---|
| 26 | `/oto/createOrder` | `:41` | `:145` | `OtoCreateReq` |
| 27 | `/oto/cancel/order` | `:57` | `:1097` | `OtoCancelReq` |
| 28 | `/oto/order/routeQuery` | `:67` | `:1246` | `OtoRouteQueryReq` |
| 29 | `/oto/cloud/directOrder` | `:102` | `:1622` | `PrintOrderReq` |
| 30 | `/oto/confirm` | `:88` | `:1444` | `BspJsonConfirmRequest` |
| 31 | `/oto/waybillintercepterCommon` | `:77` | `:1356` | `MailInterceptRequest` |
| 32 | `/fm/waybill/getTemplate` | `FmController.java:60` | `FmServiceImpl.java:330` | `WaybillGetTemplateRequest` |
| 33 | `/openNuts/monthly/createCode` | `MonthlyCodeController.java:27` | `MonthlyCodeServiceImpl.java:74` | `CreateMonthlyCodeReq` |
| 34 | `/getThirdToken` | `AuthController.java:64` | — | `ThirdCustomerRequest` |

### 6.1 `oto/createOrder`（电子面单通用取号）

**下单方式判定（两套枚举容易混淆）**：

- `platformShopId` 为空 → 走 **BSP**。
- 传了 `platformShopId` → 查系统店铺（查不到报「平台店铺 id 没有配置」）→ 按 `judgeSdtAuth` 决定走 BSP 还是**丰门**。

**幂等**：两条链路都是「**先向外部取号，拿到运单号后才做本地查重**」：

1. Redis 锁 `UNITED_STORE:OTO_ORDER_CREATE_LOCK_{运单号}:{appId}`，30s。
2. `us_fm_order` 按 `waybill_no` 查重，存在则返回 `fail("-1", "重复下单，运单号已存在")`。
3. 锁未获取也走 `fail("-1")`，**HTTP 200 不是异常**。

> 已知缺陷：`finally` 释放锁用的 key 前缀是 `BATCH_`，与加锁 key 不一致，换单号时锁不会释放，只能等 30s 过期。

**前置**：组织必须有 customerCode / checkCode；`customNumber`（月结卡）必须通过白名单校验（受 `monthCardIdSwitch` 总开关和 `temp_no_month_card_check_config` 白名单控制，命中白名单则跳过校验）；`gratuityFee` 传则必须 100–3000。

**落库**：`us_fm_order` + `us_fm_order_package_info` / `_trade_order` / `_logistics_service` / `_child_print_info`。

### 6.2 其余 O2O

- `cancel/order`：按运单号 + status=1 查 `us_fm_order`，**查不到即「不存在或已取消」，不可重复取消**；丰门单调丰门取消，BSP 单要求 `resStatus==2` 否则 `US_200004`。成功后 `status=2` 软删。
- `order/routeQuery`：**仅支持 BSP 查询**。运单不在 `us_fm_order` 且未传 phone 时报「非 o2o 单子，phone 必填」；phone 为空则取订单收寄手机号后四位。
- `cloud/directOrder`：`mainNo` **不能超过 10 条**；`trackingOrder/childOrder/parentOrder` 至少一个为 "1"；母单 + 子单按 `subWaybillNo` 逗号拆分；`bizCode` 空或 130 → `oneLandQSYR*` 模板，165 → `single165LandQSYR*`，其他报「暂不支持该模板编码」。**本接口不落库**，只返回打印报文和 accessToken（token 由顺丰开放平台获取，Redis 缓存 `expiresIn` 秒）。
- `confirm`：`source` 空默认 1（通用下单）；`source=2` 须为 o2o 单；原单是丰门单时改走「A 查 B」三方单确认逻辑。`apiResultData.success != TRUE` → 「确认接口失败」。
- `waybillintercepterCommon`：**无幂等**，同一运单重复调用会生成多张工单；写 `us_order_case_handle`（理赔、source=API、state=待处理）+ 日志表；`serviceCode` 必须命中 `CaseTypeEnum`。

### 6.3 `/fm/waybill/getTemplate`（获取电子面单模板）

- `platformShopId` 必传 → 查 `us_shop` 取 `grantId` 塞 `fmShopId` → 调丰门 `external_waybill_getTemplate`。
- 纯查询转发，**无落库、无幂等**。空 body 抛 `SYS_ERR`「响应异常」。

### 6.4 `/openNuts/monthly/createCode`（月结码生成）

- `monthCard` 必填；`timeout` 默认 300s；**`needDynamicCode` 入参被硬编码覆盖为 TRUE**（第 75 行），即一定返回动态码。
- 调月结管家生成，成功后做延迟生效回调。
- 失败：动态码解析失败 / RPC 异常 → `SYS_ERR`；**业务失败返回 `success=false` 但 HTTP 200，不抛异常**。

### 6.5 `/getThirdToken`（第三方 Token）

- 请求四个字段**全部 RSA 密文**：`source` / `userName` / `userId` / `timestamp`。
- 时间窗与通用的 15 分钟**不同**：这里超 **±180 秒**就报「时间错误」。
- 流程：`us_third_customer_config.selectBySource` → 私钥解密 → 查用户 → 请求 `nuts-auth-core` 换 `access_token`。
- **响应是裸 String token，不是 R 包装**。
- 注意：`client_secret` 硬编码在代码中；`thirdCustomerConfigDo.getUrl()` 分支只有一行 todo 日志，**实际未调用**。

---

## 7. 用户组织（2 个）

| # | 接口 | Controller:行 | Service:行 |
|---|---|---|---|
| 35 | `/openNuts/userSync` | `NutsOrgUserSyncController.java:58` | `NutsOrgUserSyncServiceImpl.java:173` |
| 36 | `/openNuts/orgSync` | `:34`（方法名为历史遗留 `createOrder`） | `NutsOrgUserSyncServiceImpl.java:81` |

**共同点：都受 nacos 开关 `verifySign`（默认 true）控制。关掉后完全不验签，仅靠报文内 appId。** 排查「签名正确却报参数错」时先确认这个开关。

- **orgSync 前缀码**：首次按 appId 查 `us_org_prefix`，无则随机生成 3 位字母并落表；下游组织编码 = `prefix + 入参 organizationCode`，原始值另存 `sourceOrganizationCode`。
- **userSync 校验**：① 监管组织 ≤50 且必须属于当前 appId 组织树；② 传 `id` 视为编辑/删除，跳过新增必填；③ 新增必填 password / organizationId / authName / lastName / isLeader / enable / roleIds；④ `organizationId` 的组织路径必须含 appId 或等于 appId，否则 `ILLEGAL_REQUEST`「该所属部门不属于当前组织的本级或子组织」。
- 下游：`/zt/open-api/nuts-user-core/*`，AES 加密传输。

---

## 8. 同城下单（9 个）

入口 `OpenicController.java`（前缀 `/tc`），实现 `OpenicServiceImpl.java`。全部走 `checkOpenicSign`。请求公共基类 `CityCommonReq`（shopId / appId / requestId / timestamp / sign）。

| # | 接口 | Controller:行 | Service:行 | 说明 |
|---|---|---|---|---|
| 37 | `/tc/createOrder` | `:39` | `:142` | 金额单位**分** |
| 38 | `/tc/queryOrderFlow` | `:56` | `:471` | 状态流 |
| 39 | `/tc/queryRiderLocation` | `:91` | `:541` | 骑手坐标 |
| 40 | `/tc/cancelOrder` | `:74` | `:496` | 取件后不可取消 |
| 41 | `/tc/queryOrderStatus` | **仅 uat 分支** `:110` | 同分支 `:650` | 最终状态与费用 |
| 42 | 订单状态回调 | `MG/CityCallBackController.java:30` | `CityCallBackServiceImpl.java:114` | 接收端 |
| 43 | 顺丰原因取消回调 | `:78` | `:236` | 接收端 |
| 44 | 订单异常回调 | `:104` | `:208` | 接收端 |
| 45 | 店铺 ID/经纬度推送 | `MG/ShopIdSyncPushService.java:68` | `MQ/ShopIdSyncPushSfKafkaListener.java:111` | 出口 |

### 8.1 `/tc/createOrder`

- **前置配置校验**：传 `senderOrgCode` → 按 (`shopId`, orgId) 精确匹配 `us_city_fast_send_conf`，不匹配报「同城店铺 ID 与寄件组织编码不匹配」；不传只按 shopId 查，命中多条则 orgId 留空。
- **落库顺序**：先生成 `orderNo` 和取货序号 → **先插 `us_order`** → 再调同城开放平台（源注释：解决三方 API 与数据库一致性问题）。
- 金额：响应 `totalPrice` / `totalPayMoney` 等**单位是分**，客户需自行转元。
- 失败：上游 `errorCode != 0` → `CREATE_ORDER_ORDER`(`US_200005`)「下单失败:{上游 msg}」。
- **幂等：代码完全没有**。没有基于 `shopOrderId` 的查重，**重复调用会产生多单**。`shopOrderId` 不传时系统自动用内部 orderNo 填充。

### 8.2 同城回调（3 个）

**必须返回 `{"error_code":0,"error_msg":"success"}`**；返回 `-1` 也是 HTTP 200，不会自动重推（代码内无重试）。

- **无鉴权**：全类没有 checkSign/token/filter，manager 侧拦截器只覆盖 `/api/bill/**`。
- 三个回调**靠 URL 区分**，不靠报文内字段：`/deliverStatusChange`、`/sfCancel`、`/riderException`（另有 `/orderComplete`、`/syncCityCreateShopResult`）。
- 幂等：按 `sf_order_id` 查不到本地单**直接 return success**（视为已删/不关心）。**所以「回调了但没更新」先检查运单号是否存在于 `us_city_mail.sf_order_id`。**
- **状态更新无版本号/时间戳比较，乱序回调会覆盖状态**；重复回调会重复发微信、重复推收单中心 —— 已知风险。
- 状态映射：回调 `order_status` 10 → 内部 1、12 → 2、15 → 4、17（complete）→ 5、异常 → 6、顺丰取消 → `status=DELETE`。

### 8.3 `/tc/cancelOrder`

**状态机前置**：`order_status == null || >= 2`（已取件）报「取件后不可取消下单」。成功后 `us_order.status = DELETE`（软删，**不改 order_status**）。

### 8.4 `/tc/queryOrderStatus`（仅 uat 分支）

- `orderType=2`（商家订单号查询）时 **`shopId` 必填**，否则 `PARMAS_HAS_ERROR`。
- 上游异常 → `SYS_ERR`「查询订单实时信息异常，请稍后重试」；上游业务失败（订单不存在、超 60 天）→ **透传上游 errorMsg**。
- 金额单位分；仅支持 **60 天内**订单。

### 8.5 店铺 ID/经纬度同步推送

- Topic `HD_UNITED_STORE_SHOP_ID_PUSH`；**白名单**：nacos `shopIdPush.oneOrgIds`，白名单外静默跳过（现仅 Maxmara 接入）。
- 触发点：批量导入店铺 ID、编辑店铺 ID、设置经纬度、批量开通 —— 均在维护动作成功后，推送异常不影响主流程。
- **action 判定**：无 → 有 = add；有 → 有 = update；**无 → 无 或半量数据 = 不推**；**无 delete**（页面无删除操作）。
- 报文：`{appId, requestId, timestamp, sign, action, orgCode, shopId, longitude, latitude}`，经纬度 WGS84。

---

## 9. 阿迪收方信息推送（1 个）

`/api/open/adi/receiver/push`，**仅 uat 分支**：`AdiReceiverPushController.java:43` → `AdiReceiverServiceImpl.java:40`。

- 处理顺序：必填校验 → **幂等**（`us_adi_receiver_info.countByOrderNo > 0` 直接返回 orderNo，**不覆盖原数据**）→ 检查 RSA 私钥配置（nacos `adi.receiver.rsa.private-key`）→ **分段解密** phone / address → 落库。
- **RSA 分段规则**：PKCS8 私钥，块大小 = 模长字节数（2048 位 = 256 字节）。明文超过 **245 字节**（256 − 11 PKCS1 padding）时，发送方必须按块加密，否则解密失败。
- 落库：`us_adi_receiver_info`；phone / address 字段带 `@CryptField`，框架拦截器落库时自动加密（代码里写的是明文）。
- 失败：字段为空、`RSA解密失败`、`服务端RSA私钥未配置`、签名/时间窗失败。

---

## 10. 推送类（2 个）

### 10.1 清单运费推送（透传丰桥 `EXP_RECE_WAYBILLS_FEE_PUSH`）

**链路**：丰桥回调入站 `/api/order/batch/feePush`（**无鉴权**）→ Kafka `HD_UNITED_STORE_FEE_PUSH_TOPIC` → 一级消费落 `us_bill_detail` / `us_bill_fee_detail`、更新订单运费 → 命中 `us_fee_push_org_config`（需 status=1 + pushUrl + appSecret 齐全）→ 二级 Kafka `HD_UNITED_STORE_WAYBILLS_FEE_PUSH` → 推客户。

**重试与超时**：

- 初始 **3 次同步尝试，间隔 500ms**；连接/读超时各 **5s**。
- 响应判定：`code=200` 成功 / **`code=400` 业务拒绝（不重试，只记 error 通知运维）** / 其他和非 JSON 均视为失败。
- 兜底：3 次全失败写 `generic_sync_retry`（businessType=`WAYBILLS_FEE_PUSH`，businessId=**orderId**）→ Saturn Job 隔日重推，每条最多 3 次，重推前重新生成 requestId / timestamp / sign。

### 10.2 店铺 ID/经纬度推送

与 10.1 同一套重试机制（3 次 × 500ms、5s 超时、code=200/400 判定），差异：

- `generic_sync_retry` 的 businessId 是**一级组织 ID**（不是订单 ID）。
- **逐条插入不合并**（运费推送同单号会合并刷新）。
- Job：`shopIdPushRetryJobHandler`。

---

## 11. 客户最常问的 12 个问题（直接可答）

### 11.1 下单报错了，但订单还能查到？

顺店通**先落库再调丰桥**。丰桥失败返回 `US_200005`，但 `us_order` 里已经有一张「已导入(0)」的单，**不会自动删除**，需要走取消接口或人工处理。这是设计如此，不是数据不一致。

### 11.2 为什么下单失败？

按概率排序（标准/店配）：

1. 寄件组织不属于该 appId 的一级组织（「寄件组织不存在」）
2. 组织未配置 customerCode / checkCode（「顾客编码,效验码没有配置」）
3. 快递产品编码已失效
4. 件数超客户上限（默认 300）、物品列表超 300 条
5. 箱号与件数不一致 / 箱号已被使用
6. 月结卡号未在顺店通验证
7. 区域城配用了签回单 / 微派 / 微签，或用了保价、代收以外的增值
8. 国补单一票多件，或缺 wpMerchantCode / wpServiceCode
9. 重复客户订单号（开启查重时 180 天内同号直接拒）
10. 运费额度不足（需审批 / 转寄付现结 / 直接拒，取决于配置）

### 11.3 重复提交会不会下重单？

**分客户**：只有 `idempotent.organizationIds` 白名单里的客户按「客户订单号 + 寄件组织」幂等，**其他客户重复提交会重复下单**。同城下单 `/tc/createOrder` 完全无幂等，一定会下重单。

### 11.4 取消订单报「订单不存在」？

大概率是 V1 取消的「先删本地再调丰桥」导致的：**丰桥失败时本地订单已经删了**，重试就查不到。先确认首次调用是否已成功删除本地单。

### 11.5 取消报「非待收件状态不能取消订单」？

`order_status ≥ 2`（已取件）就不能取消，这是业务规则不是 bug。

### 11.6 三方直连单取消失败？

用 `/cancel/orderV2`，不要用 V1。V1 会把三方单当丰桥单取消。另外韵达单超过 30 天不允许取消。

### 11.7 路由查询返回空 / 报错？

- `routeQuery`（v1）：要求订单是顺店通下的，且**下单不超 90 天**；运单不属于该 appId 也会被拒。
- `routeQuery/v2`：不查本地订单，但 **`phone` 必填**，适合 CX 等非顺店通下单场景。
- `allChannelRouteQuery` 非 SF 分支依赖三方回传的路由表，**三方没推就没有数据**。

### 11.8 全渠道路由查询为什么被拒？

v2 有付费校验：需要开通「预充值账户」（服务类型 12），且**余额 ≥ 每单费用**。余额不足报 `US_100002`，未开通报 `US_101009`。同一运单号重复查询免费。

### 11.9 地址解析为什么一直返回「地址填写不规范」？

三道闸任一不过：

1. appId 不在 `gis.appids` 白名单
2. 单次超过 50 条
3. 触发限流 —— **按条计数**，一次传 50 条扣 50 次配额（200 次/秒、50 万次/天）

### 11.10 推送没收到？

| 推送 | 排查顺序 |
|---|---|
| 清单运费 | ① `us_fee_push_org_config` 是否有该组织且 status=1、pushUrl/appSecret 齐全 ② 客户是否返回 `{"code":200}` ③ 是否返回了 400（业务拒绝，不再重试）④ 查 `generic_sync_retry` businessType=`WAYBILLS_FEE_PUSH` |
| 店铺经纬度 | ① 一级组织是否在 `shopIdPush.oneOrgIds` 白名单（**最常见原因**）② `shopIdPush.customerUrls` 是否配了接收地址 ③ 同城服务 cover=1 且 enable=1 ④ 店铺 ID 与经纬度是否两者齐全（半量不推）⑤ 页面无删除操作，删除不会推 |
| 路由推送 | ① `us_route_push_config` 是否配置（未配置不推）② 确认要的是路由推送（100/110/120/130/200/300/900）还是运单信息推送，两者 topic 不同 |

### 11.11 同城回调收到了但订单状态没变？

按 `sf_order_id` 查不到本地单**会直接返回 success**，不报错。先确认运单号在 `us_city_mail.sf_order_id` 里存在。另外**乱序回调会覆盖状态**（无版本比较），状态倒退可能就是这个原因。

### 11.12 云打印拿到的 pdf 打不开？

- 下载需带 header `X-Auth-token` = 响应里的 token
- **token 有效期 24 小时**
- `files` 顺序不可靠，**必须按 `seqNo` 排序**后打印

---

## 12. 代码缺陷与风险清单（内部用，不对外）

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | O2O 取号释放锁的 key 前缀写成 `BATCH_` | `OtoOpenServiceImpl` | 换单号时锁不释放，只能等 30s 过期 |
| 2 | 同城下单无 shopOrderId 查重 | `OpenicServiceImpl:142` | 重复调用会下重单 |
| 3 | 同城回调无验签、无乱序保护 | `CityCallBackController` | 可被伪造；状态可能倒退 |
| 4 | V1 取消先删本地再调丰桥，`@Transactional` 被注释 | `OrderConfirmServiceImpl:89` | 丰桥失败后本地已删，无法重试 |
| 5 | 下单结果查询错误码复用「取消订单失败」 | `OrderSearchServiceImpl` | 客户看到 `US_200004` 文案对不上 |
| 6 | `allChannelSearch` 文档标付费但无扣费实现 | `BspOrderSearchController:220` | 商务口径与代码不一致 |
| 7 | `confirmCheck` 是死代码 | `OrderConfirmServiceImpl:428` | 顺店通侧不校验确认状态 |
| 8 | 国补推送入站无鉴权 | `BspOrderBatchController:468`、`:976` | 任何人可调用 |
| 9 | 清单运费入站 `/order/batch/feePush` 无鉴权 | 同上 | 同上 |
| 10 | `getThirdToken` 的 client_secret 硬编码 | `AuthController` | 凭证管理风险 |
| 11 | `electric/createOrder` 构造了响应却没回吐 shipperCode | `UniversalCreateOrderController:194` | 未完成实现 |
| 12 | 运单号校验 Service 返回 null 时 Controller NPE | `BspValidateWayBillNoController` | 异常信息不友好 |
| 13 | 两个错误码同为 `US_100003`（`ILLEGAL_REQUEST` / `PARMAS_HAS_ERROR`） | `ErrorCode.java` | 客户无法区分 |
| 14 | `TestController` 暴露在生产代码 | `open-server` | 上线前需确认网关拦截 |
| 15 | `us_route_push_config` 存在 app_id ≠ org_id 的脏数据 | SIT 表 id=5、id=7 | 推送时用错误 app_id 查不到密钥，推送必然失败 |

### 12.1 待修数据：路由推送配置 app_id 与 org_id 不一致

**设计口径**：`us_route_push_config.app_id` 应当等于 `org_id`（组织 ID）。
代码用 `app_id` 去 `us_open_config` 查 SM2 公钥，两者不一致就查不到，推送直接失败。

SIT 环境实测 29 条配置中有 2 条不符合：

| id | org_id | app_id（错误值） | 组织名称 | status |
|---|---|---|---|---|
| 5 | 142928 | `VpCND4rg` | 中国联合网络通信有限公司甘肃省分公司 | 1 |
| 7 | 142941 | `93f10ac621e6451480634e207` | 郑州丹尼斯百货有限公司 | 1 |

两条的 `app_id` 在 `us_open_config` 中均不存在，对应组织（142928 / 142941）的配置是有的。
修复方式：把这两行的 `app_id` 改回与 `org_id` 一致。

**排查 SQL**（只读，确认是否还有类似数据）：

```sql
select id, org_id, app_id, org_name, status
from us_route_push_config
where app_id <> cast(org_id as char);
```

---

## 13. 下一步：知识卡建设

上述内容可拆成客户问答知识卡，格式参照 `data/cards/sdt/*.yaml`，按 `docs/knowledge-methodology.md` 的方法拆。建议卡片清单（约 40 张）：

| 分组 | 卡型 | 数量 | 示例 |
|---|---|---|---|
| 接入准备 | task | 4 | 怎么申请 appId、签名怎么算、时间戳超时怎么办、环境地址怎么区分 |
| 下单 | rule / trouble | 10 | 下单失败排查、幂等规则、箱号规则、月结卡校验、运费额度拦截 |
| 取消/确认 | rule | 4 | 取消状态机、V1/V2 区别、确认接口何时校验状态 |
| 查询 | task / trouble | 6 | 时效怎么算、运单号校验凭什么、路由查询为什么空 |
| 路由 | rule / trouble | 4 | v1/v2 区别、全渠道付费规则、重复查询免费 |
| O2O | task | 3 | 取号走 BSP 还是丰门、打印模板选择、拦截工单 |
| 同城 | rule / flow | 5 | 下单/取消/回调状态码、回调返回什么、为什么没收到回调 |
| 推送 | trouble | 4 | 运费推送没收到、店铺推送没收到、路由推送没收到、重试机制 |
| 错误码 | glossary | 3 | US_100003 到底代表什么、哪些可重试、S0000/S0002/S0008 |

卡片的 `source_ref` 直接指回本文档的章节 + 代码文件行号。

---

## 附：三份代码笔记原始文件

| 文件 | 覆盖范围 |
|---|---|
| `docs/notes/A-order.md` | 下单 / 取消 / 确认 / 子单 / 放行 / 国补推送（11） |
| `docs/notes/B-query-route-print.md` | 查询 / 路由 / 打印（14） |
| `docs/notes/C-o2o-city-callback.md` | O2O / 用户组织 / 同城 / 阿迪 / 推送（23） |
