# 顺店通开放 API · 查询(8)/路由(5)/打印(1) 代码业务逻辑笔记

> 代码基线：`eps-store-core-united-store-be`，实际检出分支 `feature/uat-branch-202608`（本地 HEAD）。
> 结论以代码为准；找不到的写「代码未见」，不做推测。路径前缀 `/api` 由网关/context-path 提供，Controller 只写方法级路径。

## 0. 通用鉴权（3 种）

| 方法 | 位置 | 规则 | 凭证表 |
|---|---|---|---|
| `checkSign` | openserver `controller/AbstractController.java:34` | appId 必须能转 Long 且为已存在组织（`queryEastOrgByIdCache`）+ `us_open_config` 有记录 + 验签 | `us_open_config`(app_id/app_secret) |
| `checkSignNoOrg` | 同上 `:55` | 只查 `us_open_config`，不校验组织 | `us_open_config` |
| `checkOpenicSign` | 同上 `:64` | 同 checkSign，入参用 `OpenicRequestBaseInfo`（仅 4 字段） | `us_open_config` |

- 验签实现 `util/CheckParamUtil.java:69`：appId/requestId/timestamp/sign 非空；timestamp 必须 10 或 13 位；与服务器时差 ±15 分钟（900000ms）；`SignUtil.check` = 四串字典序排序拼接后 MD5-32。
- 本批 14 个接口全部走 `checkSign`，唯一例外：运单号校验走 `checkOpenicSign`。

## 1. 查询 8 个接口

| # | 接口 | Controller（文件:行） | Service 实现（文件:行） |
|---|---|---|---|
| 12 | 时效查询 `/order/deliverTm` | `BspOrderSearchController.java:184` | `DeliverTmServiceImpl.java:54` |
| 13 | 运单号校验 `/wayBillNo/validate` | `BspValidateWayBillNoController.java:38` | `common/.../BspValidateWayBillNoServiceImpl.java:52` |
| 14 | 清单运费 `/order/freight` | `BspOrderSearchController.java:104` | `OrderFreightServiceImpl.java:76` |
| 15 | 地址解析 `/gis/adsp/addressIdentify` | `GisController.java:73` | `common/.../CommonGisServiceImpl.java:139` |
| 16 | 全渠道下单结果 `/order/allChannelSearch` | `BspOrderSearchController.java:220` | 复用 `OrderSearchServiceImpl.java:61` / `OrderFreightServiceImpl.java:133` |
| 17 | 下单结果 `/order/search` | `BspOrderSearchController.java:78` | `OrderSearchServiceImpl.java:61` |
| 18 | 调度信息 `/order/schedule` | `BspOrderSearchController.java:196` | `OrderScheduleServiceImpl.java:50` |
| 19 | 月结付款码查单 `/openNuts/monthly/queryMonthlyWaybill` | `MonthlyCodeController.java:39` | `MonthlyCodeServiceImpl.java:191` |

（以上 Controller 均在 `united-store-open-server/.../controller/`，Service 在 `.../service/impl/` 或 `united-store-common/.../service/impl/`。）

### 1.1 时效查询 deliverTm
- DTO：`CalcTimePromiseFreightReq`（srcAddress 必填、destAddress 必填、expressType、weight>0 才生效、volumn、consignedTime）；响应 `CalcTimePromiseFreightVO`（expressType/expressTypeDesc/deliverTime/price + 解析后省市区 code/name）。
- 规则：先过 `commonGisService.gisAddrSlip` 解析寄/收地址（调 GIS addrslip 服务）→ 组 `BspDeliverTmRequest`（searchPrice="1"，未传 consignedTime 取当前时间）→ 调丰桥 `DeliverTmService`。
- **计算口径：完全调丰桥算时效与运费，本地无费率表**。业务类型匹配：指定 expressType 精确匹配 → 未匹配降级标准快递 `"1"` → 再降级取第一条；未传 expressType 直接取第一条。
- 失败：组织无 customerCode/checkCode → 参数异常；BSP 返回 head=ERR → `ROUTE_QUERY_ERROR(US_800002)`；响应为空返回 null（R.success(null)）。
- 注意：`discountFlag`（折后价 payFreightFee）仅在 wechat/manager 内部链路启用，本对外接口未设置。

### 1.2 运单号校验 validate
- DTO：`BspValidateWayBillNoRequest`（appId/requestId/timestamp/sign/waybillNo 全 @NotBlank）；响应 `BspValidateWayBillNoResponse`（success/errorCode/errorMsg/msgData）。
- 规则：`ThirdPartyService` 模板 → 企微/丰桥预下单域名 `preorder.url`，表单 POST，`serviceCode=EXP_RECE_VALIDATE_WAYBILLNO`，签名 `MD5(msgData+timestamp+md5key)`，partnerID/md5key 来自 `PreOrderTimeConfig`；`msgData` 为 JSON。
- **不做本地校验、不查库**，纯透传丰桥判断。错误码：`S0000` 成功、`S0002` 参数错误、`S0008` 地址不可达、`S0003` 系统异常。
- Controller：msgData 非空 → `R.success(msgData)`；否则 `R.error(errorCode,errorMsg)`（service 为 null 时会 NPE，属隐患）。

### 1.3 清单运费 freight
- DTO：`OrderFreightReq`（orderNumber/mailNumber/phone）；响应 `BspOrderFreightVO`（orderId/waybillNo/customerAcctCode/meterageWeightQty/realWeightQty/volume/limitTypeCode/childNos/fees[type,name,value,paymentTypeCode,settlementTypeCode]）。
- 规则：`BspOrderFreightService` → 丰桥 `QuerySFWaybillService`；`type` 取值：有订单号→1；仅运单号且无 phone→先查 ES 换订单号 type=1；有运单号+phone→type=2 按运单号+电话尾号查。
- **计算口径：调丰桥实时查，本地无费率来源表**。失败 → `QUERY_ORDER_FREIGHT_ERROR(US_200012)`。
- 全渠道运费（`allChannelFreight`，被 allChannelFreightQuery 复用）不打丰桥：查 `us_order`(ES) → 快递鸟渠道读 `us_order_kdniao.actual_freight`；其他渠道读 `us_bill_detail`(ES,计费重量) + `us_bill_fee_detail`(DB,费用明细)。

### 1.4 地址解析 addressIdentify
- DTO：`GisBatchReq`（addressList）；响应 proxied `GisAdspResponse`（result.data 含 province/city/county/town…）。
- 规则：① appId 白名单，必须命中 nacos `gis.appids`，否则「此appid不允许访问gis」；② addressList 数量 >50 拒绝；③ 限流 `RateLimiter`（Redis 滑动窗口）：200 次/秒、500000 次/天，按 appId 计数——**注意是 for 循环里逐条判断，N 个地址消耗 N 次配额**；④ 逐条串行调 `nuts-sfapi-gis` `/gis/adsp/addressIdentify`。
- 失败：GIS 抛异常时**不报错**，返回 `status=1` + message「地址填写不规范，请重新正确填写！」+ 原地址回显。限流用 `US_1100018`。

### 1.5/1.6 全渠道下单结果 / 下单结果
- DTO：`AllChannelSearchRequest`（logisticCompanyCode 可空默认 SF、orderNumber、mailNumber）；`OrderResultReq`（orderNumber/mailNumber）；响应 `BspOrderSearchVO`（orderNumber/mailNumber/orderStatus/remark/abnormalReason）。
- allChannelSearch 先 `checkParam`：订单号与运单号至少一个；logisticCompanyCode 空则补 SF。SF → `orderSearch`；非 SF → `queryOrder`（读本地 `us_order` ES，返回状态+异常原因）。
- orderSearch 规则：组织须配置 customerCode/checkCode；订单号空则用运单号查 ES 换 custOrderNo（查不到「订单不存在」）；调丰桥 `OrderSearchService`（searchType=1）；再用返回的首个运单号查 ES 补状态。BSP 返回无 mailNumber → 返回 null；ES 无记录 → 抛「订单不存在」。
- **付费开关：代码未见**。文档标注「付费」，但两个方法均无服务开通校验/扣费/流水（对照 allChannelRouteQuery/v2 才有）。
- 失败：查询异常统一包成 `CANAL_ORDER_ORDER(US_200004)`（错误码语义是「取消订单失败」，属复用不当，对外报错文案需注意）。

### 1.7 调度信息 schedule
- DTO：`ScheduleResultReq`（orders[]、mailnos[]）；响应 `UsPushOrderStateVO`（orderNo/waybillNo/orderStateCode/orderStateDesc/empCode/empPhone/netCode/lastTime/bookTime/carrierCode/createTm）。
- 规则：用 `getOneLevelOrgCache` 取一级组织做越权归属；`orders+mailnos` 总数 >20 → `ORDER_SCHEDULE_ERROR(US_300003)`；先按运单/订单号查 ES 换 orderNo 列表，再查 `us_push_order_state`(ES) 取调度状态。空结果返回空数组。
- 落库：只读 `us_push_order_state`，不落库、不调外部。

### 1.8 月结付款码查单 queryMonthlyWaybill
- DTO：`QueryMonthlyWaybillReq`（uuid、monthlyCard）；响应 `QueryMonthlyWaybillDTO`（waybillNo、contact=电话后 4 位）。
- 规则：uuid/monthlyCard 必填；组织存在且 `enable!=0`（禁用报错）；查 `us_monthly_billing_waybill`：条件 status=1 + monthly_card_uuid + `monthly_card=SM2加密(monthlyCard)` + order_org_id + order_org_path，`limit=1000`。
- 每条运单再查顺丰运单安全接口取手机号后 4 位（`WaybillDomainService.queryByWaybillNoSecurity` → 失败降级 feign `queryMailNoSecurity`）；无手机号则 contact 为空。
- 失败：参数异常（月结卡/uuid 空）、组织不存在/已禁用。代码未见分页参数，固定最多 1000 条。

## 2. 路由 5 个接口

| # | 接口 | Controller（文件:行） | Service（文件:行） |
|---|---|---|---|
| 20 | `/order/routeQuery` | `BspOrderSearchController.java:116` | `OrderRouteServiceImpl.java:89`（checkIfBelongToSDT=true） |
| 21 | `/order/routeQuery/v2` | `BspOrderSearchController.java:128` | 同上 `:89`（false） |
| 22 | `/order/allChannelRouteQuery` | `BspOrderSearchController.java:143` | `OrderRouteServiceImpl.java:122` |
| 23 | `/order/allChannelRouteQuery/v2` | `BspOrderSearchController.java:159` | `AllChannelRouteQueryNewServiceImpl.java:87` |
| 24 | 全渠道-标准路由推送（推客户） | 出口不在 RouteController | 见 2.5 |

### 2.1 routeQuery vs routeQuery/v2（**v2 是新版**）
| 差异点 | routeQuery | routeQuery/v2 |
|---|---|---|
| 归属校验 | 本地查 ES `us_order`，校验 appId==oneOrgId/organizationId；特殊组织 `547810,492092` 可跨查 | **不查本地订单**，直接透传丰桥 |
| phone | 不要求 | **必填**，非空否则「号码不能为空」 |
| tracking_type | 固定 `2`（按客户订单号） | 有订单号→`2`；只有运单号→`1`（按顺丰运单号） |
| 超期限制 | 下单超 90 天 → `ROUTE_TIME_OUT(US_800001)` | 无此判断 |
| CX 兼容 | 否（注释「支持CX和BSP」指 v2） | 是 |

- 共同点：组织须配置 customerCode/checkCode；运单/订单号至少一个；`check_phoneNo` 取 phone；OT/EXP 特殊 appId（`isOtExp`）改走 `routeQueryOtExp`。失败统一 `ROUTE_QUERY_ERROR(US_800002)`。
- 响应 `BspOrderRouteVO`（acceptTime/acceptAddress/remark/opCode/reasonName/reasonCode）。

### 2.2 allChannelRouteQuery（v1）vs /v2（**v2 是新版+付费**）
| 差异点 | v1 `allChannelRouteQuery` | v2 `allChannelRouteQueryNew` |
|---|---|---|
| SF/空编码处理 | 走 routeQuery(true)，异常降级 routeQuery(false) | 走 v1 的 `allChannelRouteQuery`（同一底层） |
| 服务开通 | 无 | 校验 `us_service_open` 服务类型 12「预充值账户」enable=1，否则 `NOT_AVAILABLE(US_101009)` |
| 去重 | 无 | Redis 单号锁 `CX:QUERY:{appId}:{mailNo}` + 查 `us_amt_account_flow_record`(change_type=1) |
| 扣费 | 无 | 余额锁 `ORG:BALANCE:{oneOrgId}`；校验 `us_service_open_detail` 余额(类型19)≥每单费；**查询成功才扣费**，更新余额 + 写 `us_amt_account_flow_record`(流水号LS+雪花ID) |
| 落库 | 只读三方表 | 每次写 `us_route_query_record`（含 isDuplicate、IP、responseResult） |
| opCode | 原样 BSP opCode | 对 SF 额外转 `FullChannelRoutePushEnum.actionCode` |
| 重复查询 | — | 同单号再次查：免费(isDuplicate=1)，直接返回 |

- 非 SF 分支（v1/v2 共用）：`logisticCompanyCode` 须在 `LogisticCompanyEnum` 内；按运单号查本地单（母单→子单），归属不符「无法查询此运单」；快递鸟渠道 → `kdNiaoService.getOrderTracesPro` 并累加 `us_kdn_app_route_query_count`；三方直连 → 读 `us_third_order_route` 表；本地无单 → 按快递鸟月结渠道查。
- 失败：余额不足/未充值 → `SYS_ERR(US_100002)`「余额不足/该账户未充值」；锁抢占失败 → `OVERFLOW(US_100001)`。

### 2.5 全渠道-标准路由推送（顺店通 → 客户）
- **open-server `RouteController` 无对外推送出口**：仅有 `/route/register`（`:50` 路由注册）和 `/route/thirdJD/routePush`（`:58` 接收京东推送）。
- 触发链路（两条并存）：
  1) 顺丰 BSP 路由回调 → mq-consumer `OrderStatusMessageServiceImpl.routeInfoSendMQ:787` 发 Kafka `HD_UNITED_STORE_ROUTE_DISTRIBUTE_TOPIC` → `RoutePushSfKafkaListener.onMessage:43` → `RouteDistributePushServiceImpl.distributePush:54`：按运单查 ES 得组织 → 查 `us_route_push_config`(pushUrl/appId/appSecret/productId/pushType) → 按 pushType 选策略（COMMON / COMMON_ENCRYPT_INFO / ZHESHANG_BANK / SYT），HTTP POST 到客户 pushUrl，写 `us_route_push_log`（`RoutePushStrategy.java:34`）。
  2) manager `/external/routeInfo`（`RoutePushController.java:57`，供 route-push 服务调）→ `routePushSingle:6993` + `routeDistributeToTansfer:6495`：补全一级组织后调外部 feign `RouteTransferSOA.routeTransfer`（customId=oneOrgId, applicationCode），由 route-transfer 服务完成对客户推送；阿里国际单转 Kafka `HD_UNITED_STORE_ALI_ROUTE`。
- 报文构造：入参 `BspOrderRoutePushResponse`（id/orderNumber/mailNumber/acceptTime/acceptAddress/remark/opCode/platForm/toSYT）；加签 `genSign`（`CommonImplStrategy.java:135`）= [appId,appSecret,productId,id,mailNumber,orderNumber,timestamp] 排序拼接 MD5 头字段 appId/productId/timestamp/sign；`COMMON_ENCRYPT_INFO` 用客户公钥 SM2 加密表单 content。
- 标准状态映射 `FullChannelRoutePushEnum`：100 未收件/110 已收件/120 运输中/130 派件中/200 已签收/300 异常件/900 已取消，对应顺店通订单状态。
- 另有 `HD_UNITED_STORE_FULL_CHANNEL_ROUTE_PUSH` + `CustomRoutePushSfKafkaListener`（`us_waybill_push_config`）推送的是**运单信息**（重量/体积/揽收签收时间），与路由推送不是同一出口，注意区分。

## 3. 打印 1 个接口

### 3.1 云打印 `/fq/cloundPrint`
- Controller `FengmenController.java:27`；Service `CloundPrintServiceImpl.java:29`；下游 `common/.../FQCommonServiceImpl.java:35`。
- DTO：`CloundPrintReq`（templateCode @Range 1-3 必填、masterWaybillNo 必填、branchWaybillNos 逗号分隔、backWaybillNo 签回单、remark、recTelSuffix 收方后6位、sendTelSuffix 寄方后6位、isPrintLogo 默认 true、extJson{channel,encryptFlag,mergePdf,mergeType}）。
- 规则：templateCode 1/2/3 → 模板 `fm_76130_standard_` / `fm_150_standard_` / `fm_210_standard_` + `fq.customerCode`；组 documents：母单(seq=1) + 签回单 + 每张子单（排序保证母单第一、子单/签回单依次 seq）；`sum`=单据总数；`sync=true`；调丰桥云打印，header `sysCode/reqTime/signature`（`SFCloudPrintUtil.genSignature` 用 `fq.checkCode`）。
- 响应 `FengQiaoCloundPrintResponse`（success/requestId/errorCode/errorMessage/obj），obj.files[] = {url, token, waybillNo, seqNo, pageCount…}。**url 为已编码的 PDF 下载地址（GET），下载需 header `X-Auth-token`=token，代码注释标注 token 有效期 24h；files 不保证顺序，需按 seqNo 排序**。
- 失败：丰桥调用异常 → `GENERAT_PDF_ERROR(US_100047)`；templateCode 越界/主单号空 → 参数校验（`PARMAS_HAS_ERROR US_100003`）。

## 4. 典型失败原因与错误码速查

| 错误码 | 枚举 | 常见场景 |
|---|---|---|
| US_100003 | PARMAS_HAS_ERROR（与 ILLEGAL_REQUEST 同码，历史遗留） | appId 非法/未配置、必填缺失、运单号不可查、越权「无法查询此运单」 |
| US_800001 | ROUTE_TIME_OUT | routeQuery 下单超 90 天 |
| US_800002 | ROUTE_QUERY_ERROR | 路由/时效查询失败、快递鸟查询失败 |
| US_200012 | QUERY_ORDER_FREIGHT_ERROR | 清单运费查询失败 |
| US_200004 | CANAL_ORDER_ORDER | **下单结果查询异常实际复用了「取消订单失败」码** |
| US_300003 | ORDER_SCHEDULE_ERROR | 调度查询单号超 20 条 |
| US_101009 | NOT_AVAILABLE | 全渠道路由 v2 服务未开通 |
| US_100001 | OVERFLOW | 全渠道路由 v2 单号锁/余额锁抢占失败 |
| US_100002 | SYS_ERR | 余额不足/未充值/扣费失败 |
| US_100047 | GENERAT_PDF_ERROR | 云打印失败 |
| US_1100018 | 限流 | GIS 地址解析触发限流 |
| 000002 | YUN_MARKET_PARAMS_ERROR | GIS appId 未授权、地址超 50 条 |

## 5. 值得写进客户知识库的业务点
- **运单号校验是纯透传**：不查顺店通库，格式与可达性由丰桥判定；关注 S0002（参数）/S0008（地址不可达）/S0003（系统异常），S0000 才算合法。
- **路由查询返回空 ≠ 接口故障**：routeQuery 会因「下单超 90 天」「运单不属于该 appId」「本地 ES 无此单（含子单也未匹配到母单）」而直接报错或返回空；allChannelRouteQuery 非 SF 分支依赖 `us_third_order_route` 表，三方单未回传路由时也会为空。
- **routeQuery/v2 是「免本地校验」版**：只需要运单号 + 电话后 4 位即可查丰桥，适合非顺店通下单（CX）场景；v1 必须先在本地下过单。
- **时效/运费是丰桥实时算**：不要问「费率表在哪」，本地没有计费规则；运费明细（所有渠道运费）才来自账单表 `us_bill_fee_detail`。
- **全渠道路由 v2 按单号去重计费**：同一运单号首次查询成功才扣一次预充值余额，重复查询不再扣费；余额不足/未开通服务会直接拒绝。
- **全渠道下单结果查询文档标「付费」但代码未扣费**：接入前与商务确认实际计费口径，勿以文档推断。
- **地址解析有 3 道闸**：appId 白名单、单次≤50 条、按 appId 限流（200/秒、50 万/天，且逐条计数，50 条=扣 50 次）；解析失败不抛错，返回「地址填写不规范」。
- **云打印 url 有效期**：PDF 下载链接需带 token（代码注释 24h），files 顺序不可靠需按 seqNo 排序；母单/子单/签回单会在一次请求内合并返回。
- **月结付款码查单固定最多 1000 条**，contact 只回手机号后 4 位（顺丰运单安全接口取不到时为空）。
- **路由推送是「客户先配 URL」**：地址、appSecret、productId 存在 `us_route_push_config`，未配置则不推；推送用标准状态码(100/110/120/130/200/300/900)而非顺丰原始 opCode。
