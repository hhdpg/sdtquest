# A 组：下单 / 取消 / 确认 / 子单 / 放行 / 国补推送（11 个接口）

> 仓库：`eps-store-core-united-store-be`；模块 `united-store-open-server`（对外网关，context-path `/api`）、`united-store-manager`（国补推送）。
> 下列行号基于当前工作区（分支 `feature/uat-branch-202608`）。

## 0. 总览

| # | 接口 | Controller:行 | Service 实现 | 鉴权 |
|---|------|---------------|--------------|------|
| 1 | POST /api/universal/createOrder | UniversalCreateOrderController.java:134 | UniversalCreateOrderServiceImpl.java:298（source=1） | checkSign |
| 2 | POST /api/universal/electric/createOrder | 同文件:194 | 同上:298（SF，source=2）/ createThirdMonthlyOrder:1292（三方） | checkSign |
| 3 | POST /api/universal/electric/createOrderV2 | 同文件:228 | 同上 + mergeOrderAuto:2836 | checkSign |
| 4 | POST /api/universal/createOrderXns | 同文件:159 | 同 1 + saveHennessyOrderMapping:1269 | checkSign |
| 5 | POST /api/preorder/times | PreOrderController.java:38 | PreOrderServiceImpl.java:41（buildRequest:52） | checkOpenicSign |
| 6 | POST /api/cancel/confirm | BspOrderConfirmController.java:69 | OrderConfirmServiceImpl.java:358 → OpenOrderTransactionalServiceImpl:96 | checkSign |
| 7 | POST /api/open/subWaybillNumber/apply | BspCreateOrderController.java:88 | OrderZDServiceImpl.java:88 | checkSign |
| 8 | POST /api/cancel/order | BspOrderConfirmController.java:43 | OrderConfirmServiceImpl.java:89 | checkSign |
| 9 | POST /api/cancel/orderV2 | BspOrderConfirmController.java:56 | OrderConfirmServiceImpl.java:150 | checkSign |
| 10 | POST /api/delivery/trigger | BspDeliverNoticeController.java:42 | OpenBspDeliveryNoticeServiceImpl.java:36 → BspDeliveryNoticeServiceImpl | checkSign |
| 11 | POST /api/order/batch/countrySubsidyPush | BspOrderBatchController.java:976 | BspOrderBatchServiceImpl.java:7954 | 代码未见 |

不支持 `checkSignNoOrg`：全仓仅 `YuntaController` 注释处出现，无实际启用。

### 鉴权细节（checkSign / checkOpenicSign）
- `AbstractController:34 checkSign` → 校验路径：`appId` 可转 Long → 组织存在（`queryEastOrgByIdCache`）→ `us_open_config` 有记录（`app_secret`）→ `CheckParamUtil.check`。
- 签名算法 `SignUtil`：`MD5_32( sortAsc(appId, requestId, timestamp, appSecret) 拼接 )`。
- `timestamp` 支持 10/13 位，与服务器时差超 ±15 分钟报 "request timestamp timeout 15 minutes"；缺任一参数报 "appId or requestId or timestamp or sign is empty"。
- 凭证表：`us_open_config`（app_id / app_secret / public_secret / private_secret）。组织侧凭证在 `us_order.client_code/check_word` 对应组织 `customerCode/checkCode`（用于调用丰桥 BSP）。
- 错误码坑：`PARMAS_HAS_ERROR` 与 `ILLEGAL_REQUEST` 都是 `US_100003`（枚举重复定义，SignUtil 失败落到"非法请求"文案）。

---

## 1. /api/universal/createOrder（标准下单，仅顺丰）

- 入口 `UniversalCreateOrderController:135`；Service `UniversalCreateOrderServiceImpl:298`（source=1）。
- DTO：`UniversalCreateOrderReq extends RequestBaseInfo`（+appId/requestId/timestamp/sign）。
  关键字段：`orderNumber` 客户订单号、`costType` 成本类型(非 PERSON 必须传收件组织)、`senderOrgCode` 必填、`payMethod` 1寄付/2到付/3三方/4寄付现结、`expressType` 产品、`parcelQuantity` 件数、`boxNo` 箱号、`sendStartTime` 预约取件、`needReturnTrackingNumber` 0-3、`cargo` 物品、`addedService` 增值、`otherInfoList` 扩展(含国补)、`crossBorderFlag/senderRegion/recRegion` 港澳台、`monthlyCustomerId` 收方优惠付、`deliveryAfterCompleted + clientPlanId` 到齐派送。
- 响应：`R<BspOrderResponse>`（orderNumber / mailNumber(母,子) / mailMapBoxNo / returnTrackingNumber / rlsInfo 面单路由数据 / isBudget / isBudgetMessage / isOrderAmountPayment）。
- 核心规则（按执行顺序）：
  1. `checkParam`：costType/senderOrgCode/payMethod/expressType/needReturnTrackingNumber 必填；`expressType` 命中失效列表 `EXPRESS_TYPES` 直接拒；件数默认 1，上限按客户 `customerLimitConfig.getOrderLimit`（默认 300）；物品列表 ≤ `maxZdNum`（默认 300，shdt 客户 800）；箱号 ≤1000 且长度 1-50、与件数一致、重复需看箱号校验开关；回单内容 ≤6 字；`trackingItems` 需为 1-4 数字；微派+微签不可同选；`customNumber` 必须在月结卡号白名单；`monthlyCustomerId` 仅允许到付且需在 `us_receiver_pay_rule_config` 中；区域城配(331) 只允许 INSURE/COD 增值且禁签回单/微派/微签；国补 `otherInfoList` 含 subsidySource 时强制一票一件且 wpMerchantCode/wpServiceCode 必传；TDELIVERY 定时派送 value/value1/value2 强校验。
  2. 组织校验：寄件组织必须归属 `appId`（一级组织），否则 "寄件组织不存在"。
  3. 额度管控：`ORDER_FEE_LIMIT` 服务开通 + payType/costType 命中 → 按 `us_freight_budget_limit` 余额判定，超额三种策略：需审批 / 转寄付现结(4) / 禁止下单(直接返回 isBudget=true，不落单)。
  4. 幂等：仅当 appId 在 `idempotent.organizationIds` 且传了 orderNumber 时生效，key = custOrderNo + 寄件组织Id；命中则复用历史订单号（仍会重新向丰桥下单，结果回写原单，并非严格幂等）。
  5. 重复单校验：`app.default.dulpCreateCheckFlag=true` 且客户码=`app.default.customerCode` 时，近 180 天同 custOrderNo 直接 "订单号重复，不允许下单"。
  6. 先落库：`insertUsOrder`（`AbstractService.buildUsOrderDo:366`）写 `us_order`（order_source=4 开放平台、order_status=0 已导入、enter_type=接口、order_type=普通单）。
  7. 调丰桥：`createOrderToBsp:1675` → `BspOrderCreateService`（service=`OrderService`）；`isDoCall=1`（传了 sendStartTime）走 `serviceCheckPickupTime`。若配置了 `CALL_ORDER_CONVERSION_CALL_HOURS` 且丰桥返回"非营业时间"，自动改约后重试一次。
  8. 回写：成功则 order_status=1 未收件、写主/子运单号、`us_sub_mail`（子单，按 subMailNo 幂等）、`us_merge_order_mail_box_mapping`（箱号映射，可按箱号唯一性开关跳过重复）、`us_order_extra`、`us_mail`。
  9. MQ：Kafka `HD_UNITED_STORE_CREATE_ORDER_GIS`（GIS 解析）、`HD_UNITED_STORE_ORDER_FLOW`（CREATED）、`us_sub_mail` 落库后向"智慧快递助手" `storePushToZhkdzsOrderPoolOutput`（需开通 SMART_EXPRESS_ASSISTANT）；微派/微签命中时发 `weipaiOmsOrderMessageOutput`；`pushFaceFlag=1` 且 templateCode ∈ {150,210} 时发 `storePdfPushOutput`（延迟 10s）。OT/轩尼诗客户跳过这三个异步推送。
- 失败原因：`US_100003` 参数异常（大量具体文案）、`US_200005` 下单失败(包裹丰桥/内部异常)、`US_1100015/1100016` 三方配置缺失/三方下单失败、`US_100002` 未预期系统异常。
- 重要副作用：落库先于调丰桥，丰桥失败时订单仍在 `us_order` 里停留为"已导入(0)"，不会自动删除。

## 2. /api/universal/electric/createOrder（顺丰单 + 三方月结单）

- 入口 `UniversalCreateOrderController:195`；`shipperCode` 为空默认 `SF`。
- 三方分支（shipperCode≠SF）：`createThirdMonthlyOrder:1292`。DTO `UniversalCreateElectricOrderReq extends UniversalCreateOrderReq`，增加 `shipperCode`、`senderAddr/receiverAddr{province,city,county,address}`、`commodities[{no,name,count,unit,weight,amount,currency,...}]`、`addServices`。
  - 校验 `checkParamThirdMonthlyOrder:699`：物流编码有效、expressType/payMethod/收寄地址/件数必填、港澳台拒、物品名必传、箱号规则、payMethod 1→3（快递鸟寄付月结编码）。
  - 配置取自 `us_kdn_third_logistics_config`（按 appId 递归查组织的物流公司配置）；无配置抛 `US_1100015`。
  - 实际下单 `CommonThirdMonthlyOrderServiceImpl:92`（快递鸟月结 / 三方直连），落库 `BaseThirdOrderServiceImpl.saveOrder:119`（`us_order` + `us_order_cargo` + `us_sub_mail` + 箱号映射，order_classify 三方直连/物流中间平台/快递鸟月结），电子面单异步上传 OBS（`asyncSaveElectWaybillOutPut`）。此后没开通渠道抛 `DICTIONARY_ITEM_MISSING`。
  - 返回 orderNumber=三方 orderCode，mailNumber=母单号[,子单号]。
- 顺丰分支：`buildReqParam` 补全省市区/联系人（缺信息时从组织补全），`checkParam` 同标准，`universalCreateOrder(req,2)`，不回写 `us_electric_order`（只有 V2 回写）。
- 差异：不判调度规则、不判自动合单、不校验区域城配；代码里构造了 `ElectricOrderResponse` 但最终 `return R.success(response)`，即 shipperCode 未回吐（可视为未完成实现）。

## 3. /api/universal/electric/createOrderV2（店配下单，能力最全）

- 入口 `UniversalCreateOrderController:229`，Service 同 `universalCreateOrder(req,2)` + `mergeOrderAuto:2836`。
- 前置：`calcTotalWeightAndVolume:519`（物品名必传；总重/总体积取入参，否则取 items 汇总，SF 单体积不设默认，非 SF 默认 0.01 m³）。
- 调度规则：`CommonDispatchMatchService.getMatchConf` 按寄件组织/货物/收件组织匹配 `us_dictionary_item_relation`，命中后**用规则里的物流公司和产品覆盖入参**（优先规则 > 入参 > SF）。
- 三方分支同第 2 条；顺丰分支额外：`checkExpressType:468`（区域城配：非和兆客户必须传 areaCityDeliveryOrderType，和兆客户强制共配；禁签回单/微派/微签；只允许 INSURE/COD）、寄件组织必须存在、remark ≤200、`needControlOperation` 只允许 `label.sopLabel` 白名单内的 SOP 标签。
- 自动合单：`managerFeign.mergeOrderAutoRules` 判定 mergeType（0 收寄组织相同 / 1 寄件组织+收件人信息相同 / 2 相同订单号）、波次时间窗内查 ES，命中则转 `orderZDService.orderZD(req, checkDupBoxNoFlag)` 追加子单；箱号重复且开启重试时返回历史单（message 带"箱号xx重复下单，返回上一次运单号"），否则 message 带"满足自动合单规则，进行追加子单操作"。
- 落库：成功后额外 `insertUsElectricOrder:451` 把 rlsInfo 存 `us_electric_order` 临时表（主单号维度，供后续查询面单路由）。
- OT 客户（`ot.appIds`）：跳过异步推送；`ot.appIds` 命中时返回结果被改造成 `rlsInfo` 假数据（originCode/destCode=573、filterResult=2、remark="3:国庆电商高峰"），属测试/占位逻辑。
- 差异 vs V1：多了调度规则覆盖、自动合单、区域城配与 SOP 校验、`us_electric_order` 临时表、OT 特殊返回。

## 4. /api/universal/createOrderXns（轩尼诗）

- 入口 `UniversalCreateOrderController:160`；逻辑 = 标准下单 + 成功后 `saveHennessyOrderMapping:1269`。
- 额外字段 `pickupUrl`（提货单 URL）。落库 `us_hennessy_order_mapping`（waybill_no / customer_order_no / pickup_url / one_org_id）。
- 落库失败只打日志不回滚（try-catch 吞异常），下单本身照常成功。
- 轩尼诗 appId 命中 `ot.hennessyAppIds` 时：下单走专用地址 `ot.hennessyCreateOrderUrl`（`OtExpServiceImpl.getCreateOrderUrl:76`），并跳过微派/微签/面单异步推送（`isHennessyExp`）。
- 下单失败原因同标准下单；映射表相关无错误码（静默）。

## 5. /api/preorder/times（顺丰预下单取件时间）

- 入口 `PreOrderController:39`；Service `PreOrderServiceImpl:41`。
- 鉴权：`checkOpenicSign`（同样校验组织 + us_open_config + MD5 签名）。
- DTO `PreOrderRequest`：`orderId` 客户订单号、`cargoName` 托寄物、`monthlyCard` 月结卡号、`expressTypeId` 产品、`contactInfoList` 收寄双方。
- 下游：顺丰标准服务 `EXP_RECE_PRE_ORDER`，form-urlencoded，`partnerID + msgDigest(MD5(json+timestamp+md5key))`，地址 `preorder.url`（默认 sit std/service），支持 sfproxy 开关。
- 响应：成功返回 `List<PreOrderMsgData>{serviceDate, startTime, endTime}`；失败 `R.error(HTTP 417, errorCode, errorMsg)`。
- 错误码（顺丰侧透传）：`S0000` 成功 / `S0002` 参数错误 / `S0008` 地址不可达 / `S0003` 系统错误。
- 不落库、不发 MQ，纯查询。

## 6. /api/cancel/confirm（顺丰订单确认）

- 入口 `BspOrderConfirmController:70`；Service `OrderConfirmServiceImpl.orderConfirm:358` → `OpenOrderTransactionalServiceImpl.orderConfirm:96` → `BspOrderConfirmService`（service=`OrderConfirmService`，dealType=1）。
- DTO `ConfirmInfoReq`：`orderNumber`/`mailNumber`（可只传运单号，代码会反查 custOrderNo）、`weight`、`expressType`、`childrenNumbers`、`volume`、`isConfirmNew`(1 改联系人/2 改其他客户订单)、`checkMonthlyCard`、`returnTracking`、`waybillSize`、`isGenEletricPic`、`extraInfoList`。
- 校验：appId→组织，组织 `customerCode/checkCode` 必须配置；国补单以 `extraInfoList` 含 `subsidySource` 为准，需 wpMerchantCode/wpServiceCode；若只传 mailNumber 且是国补单，订单状态 >3（派送中及以后）报 "国补订单只能在派件前修改订单"。
- 注意：确认接口**不做**顺店通侧状态前置校验（`confirmCheck:428` 为死代码，无调用方），状态是否允许确认由丰桥判定；未成功（resStatus≠2）统一抛 `US_200004` 取消订单失败 / "bsp订单确认返回不成功"。
- 落库：仅 `us_open_request_log` 请求日志；订单主体由丰桥回写/后续路由推送更新。

## 7. /api/open/subWaybillNumber/apply（子单号申请）

- 入口 `BspCreateOrderController:89`；Service `OrderZDServiceImpl.orderZD:88`（`checkDupBoxNoFlag=false`）。
- DTO `OrderZDReq`：`orderNumber` 必填 ≤64、`parcelQuantity` 新增件数 1-20 必填、`boxNo` 箱号、`orderNo` 系统订单号（可选，指定后按 orderNo 定位）。
- 前置条件（重点）：
  1. appId 组织必须已配置 `customerCode/checkCode`，否则 "顾客编码,效验码没有配置"。
  2. 母单原有箱号需与新申请箱号一致：母单有箱号则子单必须传箱号，母单无箱号则子单不允许传箱号。
  3. 箱号 ≤1000、长度 1-50、不可重复、数量必须等于新申请件数。
  4. 箱号全局唯一性：按 `getBoxNoCheckDaysIfOpen`，>0 限天数、=0 全量、<0 跳过；命中已用箱号直接 `US_100003` "子单申请中有箱号已被使用"。
- 下游：`BspOrderZDServiceImpl`（service=`OrderZDService`）；OT 客户走 `otExpService.orderZDOtExp`（EXP_RECE_GET_SUB_MAILNO）。
- 落库：更新 `us_order.parcel_quantity`（累加）、`mailno`（累加子单号）、`us_sub_mail`、箱号映射（`us_merge_order_mail_box_mapping`，type 1母/2子）。
- MQ：`storePushToZhkdzsOrderPoolOutput`（智慧快递助手）。
- 失败：`US_1000001` 子单号申请失败（包裹丰桥原始错误描述，如 8018 订单不存在、8028 未配置业务）。

## 8. /api/cancel/order（取消订单，V1）

- 入口 `BspOrderConfirmController:44`；Service `OrderConfirmServiceImpl.orderCanel:89` → `OpenOrderTransactionalServiceImpl.cancelOrder:62` → `BspOrderConfirmService`（dealType=2）。
- DTO `OrderConfirmReq`：`orderNumber` 客户订单号、`mailNumber` 运单号、`dealType`(内部强制 2)、`extraInfoList`（国补时 subsidySource 必须="cancel"）。
- 定位订单 `check:307`：优先 custOrderNo 查 ES，否则按 mailNumber 查。
- 状态机限制（严格）：
  - 订单 `order_status` 为空或 ≥2（已取件）→ `US_200002` "非待收件状态不能取消订单"。
  - `order_status=6 异常件` 且 abnormal_reason="客户已取消寄件" → `US_200020` "此单已取消，不可重复取消"。
  - `one_org_id != appId` → `US_200003` "只能操作本门店订单"。
  - `order_source != 4` → `US_200010` "只能取消开放平台创建的订单"。
- 执行顺序（重要）：**先在顺店通侧软删除订单**（`StatusEnum.DELETE`，并删 ES、子运单）→ 再调丰桥取消。若丰桥失败，抛 `US_200004`，但订单在顺店通已是删状态（无回滚，`@Transactional` 被注释）。
- 落库表：`us_order.status=2`、`us_sub_mail` 软删、`us_open_request_log`。
- 失败：`US_200001` 订单不存在、`US_200004` 取消订单失败、`US_100003` 参数异常。

## 9. /api/cancel/orderV2（取消订单，支持三方直连）

- 入口 `BspOrderConfirmController:57`；Service `OrderConfirmServiceImpl.orderCanelV2:150`。
- 与 V1 相同的前置 + 定位 + 状态校验（共用 `check`），差异在取消通道：
  - `us_order.channel == THIRD_DIRECT`（三方直连月结）→ 走 `cancelOrder(UsOrderDo):191`：`OrderFeignClient.cancelOrder` 取消德邦(DBL)/韵达(YD)等三方；YD 超过 30 天拒（"超过一个月了,不能取消订单了"）；成功后才软删订单 + 子运单 + 发订单操作日志 Kafka `HD_UNITED_STORE_ORDER_OPERATION_LOG`；三方返回空/非 0 错误码 → resStatus=1 + failedReason（不删单）。
  - 其余渠道 → 同 V1 丰桥取消（先删后调）。
- 三方配置取自 `us_kdn_third_logistics_config`（递归组织查找），缺失时仍会调用三方接口（配置只用于填充凭证）。
- V1 vs V2 一句话：V1 只支持丰桥自营单；V2 对三方直连单改走三方公司取消接口，不再调丰桥。

## 10. /api/delivery/trigger（订单放行 / 退回通知）

- 入口 `BspDeliverNoticeController:43`；Service `OpenBspDeliveryNoticeServiceImpl.trigger:36` → `BspDeliveryNoticeServiceImpl`（service=`DeliveryNoticeService`）。
- DTO `OrderDeliverNoticeReq`：`waybillNo` 运单号（必填，为空报 "运单号不能同时为空"）、`dataType` **71=派送通知(放行) / 72=通知退回**。
- 校验：appId→组织存在，组织 `customerCode/checkCode` 必须配置；二者作为 accessCode/checkword 透传丰桥。
- 副作用：无本地落库、无 MQ，纯转发丰桥；响应 `BspDeliveryNoticeResponse{status}`，丰桥 head=ERR 时抛 `BSP_OPERATION_FAILED`（原始错误描述透传）。
- 典型失败：appId 非法、组织未配置顾客编码/校验码、运单号不存在或状态不允许（丰桥侧）。

## 11. 国补订单信息推送（顺店通 → 客户；由顺丰/BSP 触发）

- 入口 `BspOrderBatchController:977`（模块 manager，路径 `/api/order/batch/countrySubsidyPush`）；Service `BspOrderBatchServiceImpl.pushCountrySubsidyInfo:7954`。
- 鉴权：**代码未见**任何签名/验签（`BspBaseRequest` 里的 msgDigest/nonce/timestamp 未被读取校验）；manager 侧拦截器仅覆盖 `/api/bill/**`。
- 报文来源：`BspBaseRequest.msgData`（JSON 字符串）→ `CountrySubsidyInfoRequest`：`waybillNo` 必填、`imei`（3C 国补）、`sn`（3C）、`wpServiceCode`（微派任务码）、`photoList[{photoUrl(加密),photoType(1-8),photoTime,scanContent}]`、`scanResult[{code,details[{verifyCode,createTime,status}]}]`（家电国补，status=UNVERIFIED/VERIFIED/SUPPLEMENT）。
- 处理流程：
  1. waybillNo 为空 → `success=false,retryFlag=false,errorCode=1000,"msgData数据不存在"`；
  2. 按运单号查 ES，无单 → "运单号不存在"；
  3. 查 `us_customer_address_config`（one_org_id 维度，需 url + secret_key），无配置 → "客户地址配置不存在"；
  4. `photoUrl` 用该客户的 **secretKey 做 AES256 解密**（`AES256CipherUtil`，16 字节全 0 IV），失败 → "图片解密失败"；
  5. POST JSON 到客户 url（支持 sfproxy），透传客户返回体；空响应/异常 → `success=false,retryFlag=false,"推送失败"/"推送客户失败"`。
- 触发条件：代码内无定时任务/无 MQ 消费入口，仅由顺丰/BSP 主动回调；具体哪一步（签收/派件/核销）触发在本仓库**代码未见**（需丰桥侧确认）。
- 响应 `CountrySubsidyInfoBspVO{success,retryFlag,errorCode,errorMsg}`；`buildVO:8013` 中 retryFlag 恒等于 success。

---

## 值得写进客户知识库的业务点

- **下单失败最常见原因（标准/店配）**：寄件组织不属于该 appId 一级组织；快递产品编码已失效；件数超客户上限（默认 300）；物品列表超 300 条；箱号与件数不一致 / 箱号已被使用；月结卡号未在顺店通验证；区域城配用了签回单/微派/微签或非保价/代收增值；国补单一票多件或缺 wpMerchantCode/wpServiceCode；重复客户订单号（开启查重时 180 天内同号直接拒）。
- **下单成功但先落"已导入"状态**：顺店通先落库再调丰桥，丰桥失败会返回 US_200005，但顺店通里能查到一张"已导入(0)"的单，需要走取消或人工处理，不会自动消失。客户端排查"下单报错但订单存在"时以此解释。
- **幂等只在白名单客户生效**：仅 `idempotent.organizationIds` 配置的客户按"客户订单号+寄件组织"幂等；其他客户重复提交会重复下单（若未开查重）。开启箱号唯一性校验的客户，重复箱号会被拦截或返回上次运单号（V2 自动合单）。
- **取消与确认的时序要求**：取消只允许"已导入/未收件"（order_status<2），已取件后不可取消；只能取消 order_source=4 开放平台单；只能操作本组织单；已因"客户已取消寄件"变异常的单不可重复取消；国补取消必须带 subsidySource=cancel。确认接口在顺店通侧不校验状态，状态合法性由丰桥判定，国补单仅允许派件前修改。
- **V1/V2 取消区别**：三方直连月结单必须用 /cancel/orderV2（V1 会把三方单当丰桥单取消而失败）；V2 韵达单超过 30 天不允许取消。另需提醒：V1 取消是"先删本地单再调丰桥"，丰桥失败时本地已删，重试会返回订单不存在。
- **子单申请前置条件**：母单已存在且已配置顾客编码/校验码；母单有箱号则子单必须带箱号、母单无箱号则子单不能带；箱号数量必须等于新增件数（1-20 件/次）；箱号受全局唯一性窗口限制，重复会被拒；一次申请最多 20 件。
- **放行/退回**：dataType=71 放行派送、72 通知退回；只能对已存在的运单发起，纯转发丰桥，无本地状态留存，重复发起以丰桥返回为准。
- **预下单只查时间**：/preorder/times 只返回可选取件日期与时间段，不占运单号、不落库；错误码 S0002 参数错、S0008 地址不可达。
- **国补图片解密**：推送给客户的 photoUrl 是加密串，需用顺店通为该客户分配的 16 位 secretKey 做 AES256 解密（IV 全 0），url 有效期 24 小时；回调报文里 success=false 且 retryFlag=false 表示不要重试，看到 1000 多为报文/配置/运单号问题。
- **国补推送异常排查三板斧**：① 运单号能否在顺店通查到；② 该客户是否配置了 `us_customer_address_config`（url + secret_key）；③ 图片解密密钥是否与顺丰分配的一致。
