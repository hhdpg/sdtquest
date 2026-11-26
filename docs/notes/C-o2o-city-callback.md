# 顺店通对外 OpenAPI 业务逻辑笔记 C 组（O2O 9 + 用户组织 2 + 同城 9 + 阿迪 1 + 推送 2 = 23）

> 仓库 `/Users/xie_cd/workproject/eps-store-core-united-store-be`，分支 `feature/v3.68.5`（本地 worktree 当前检出的是 `feature/uat-branch-202608`，两者上述文件除 2 个接口外内容一致）。
> 路径简写：`OS` = `united-store-open-server/src/main/java/com/sf/united/store/openserver`，`MG` = `united-store-manager/src/main/java/com/sf/united/store/manager`，`MQ` = `united-store-mq-consumer/src/main/java/com/sf/united/store/consumer`。
> 应用级 servlet context-path 均为 `/api`（`openserver/bootstrap.yml:8`、`manager/bootstrap.yml`），故文档路径 `/api/xxx` 与 `@RequestMapping("/xxx")` 叠加一致。

---

## 0. 通用鉴权机制（先读这一节）

| 鉴权方法 | 位置 | 校验内容 | 凭证表 |
|---|---|---|---|
| `checkSign(req, uri)` | `OS/controller/AbstractController.java:34` | ①appId 转 Long → `OrgService.queryEastOrgByIdCache` 必须存在；②`us_open_config` 按 appId 取 appSecret；③`CheckParamUtil.check` 验签 | `us_open_config`（appId/appSecret/status） |
| `checkSignNoOrg` | `AbstractController.java:55` | 同 checkSign，但**跳过组织存在性校验**（本组 23 接口均未使用，代码中仅 YuntaController 注释掉） | 同左 |
| `checkOpenicSign` | `AbstractController.java:64` | 组织存在 + `us_open_config` + `CheckParamUtil.checkOpenicSign`（同城链路专用） | 同左 |
| 第三方 RSA | `OS/controller/AuthController.java:64` | 私钥解密 timestamp/userId/userName；`us_third_customer_config` by source | `us_third_customer_config`（source/pubKey/priKey/roleId/url） |

- 签名算法 `SignUtil.sign`（`united-store-shop/.../util/SignUtil.java:31`）：`[appId, requestId, timestamp, appSecret]` 数组字典序排序 → 直接拼接 → MD5 32 位小写。**业务字段与 URI 不参与签名**。
- 时间窗 `CheckParamUtil.checkBaseParam`（`OS/util/CheckParamUtil.java:69`）：timestamp 必须 10 或 13 位；与服务器时间差 > ±900000ms（15 分钟）报 `request timestamp timeout 15 minutes`。
- 缺参报错统一 `PARMAS_HAS_ERROR`（`US_100003`，「参数异常」）；验签失败为 `ILLEGAL_REQUEST`（同为 `US_100003`）。全局异常由 `OS/aspect/GlobalExceptionAdvice.java:117` 把 `BizException` 转为 HTTP 500 + `R.error(errorCode, message)`。
- **注意**：`checkSign` 只校验 appId 是否为合法组织、签名是否正确，**不校验 appId 与报文内业务对象（店铺/运单）的归属关系**（归属校验散落在各 Service 内）。

---

## 1. O2O（OtoOpenController，`@RequestMapping("/oto")`）

入口文件：`OS/controller/OtoOpenController.java`；实现：`OS/service/impl/OtoOpenServiceImpl.java`（2008 行）。

| # | 接口 | Controller | Service | 请求 DTO | 响应 DTO |
|---|---|---|---|---|---|
| 1 | `/api/oto/createOrder` | `OtoOpenController.java:41` | `OtoOpenServiceImpl.java:145` `createOrder` | `OtoCreateReq` | `OtoOpenResponseVo`(wayBill/subWayBills/success/msg/code) |
| 2 | `/api/oto/cancel/order` | `:57` | `:1097` `cancelOrder` | `OtoCancelReq`(mailNumber) | `OtoOpenResponseVo` |
| 3 | `/api/oto/order/routeQuery` | `:67` | `:1246` `routeQuery` | `OtoRouteQueryReq`(mailNumber/phone/platformOrderNo) | `List<BspOrderRouteVO>` |
| 4 | `/api/oto/cloud/directOrder` | `:102` | `:1622` `cloudPrint` | `PrintOrderReq`(mainNo≤10/parentOrder/childOrder/trackingOrder/bizCode) | `SFCloudPrintVO` |
| 5 | `/api/oto/confirm` | `:88` | `:1444` `confirm` | `BspJsonConfirmRequest` | `BspJsonUpdateOrderResponse`(resStatus/mailNumber/orderNumber) |
| 6 | `/api/oto/waybillintercepterCommon` | `:77` | `:1356` `waybillintercepter` | `MailInterceptRequest`(wayBillNO/serviceCode/月结卡/改址) | `R.success()` 空 |

### 1.1 createOrder（电子面单通用取号）核心规则
- **鉴权**：`checkSign`。若传 `customNumber`（月结卡号）→ `CommonCustomNumberService.countCustomNumberListByOneOrgId(appId, customNumber)` < 1 直接报「月结卡号未验证」（该服务有 `monthCarIdSwitch` 总开关与 `temp_no_month_card_check_config` 白名单，命中则直接返回 10 跳过校验，见 `CommonCustomNumberServiceImpl.java:314`）。
- **下单方式判定（两套枚举容易混淆）**：
  - 若 `platformShopId` 为空 → `orderMenthod=1` → 走 **BSP**（`FmOrderMenthodEnum`:0=丰门,1=BSP；落库 `us_fm_order.order_source` 用的是 `FmOrderSourceEnum`:1=丰门,2=BSP，见 `saveFmBspOrder`）。
  - 若传了 `platformShopId` → `usShopDoMapper.selectByPlatShopIdAndOneOrgId` 查系统店铺（查不到报「平台店铺id没有配置」）→ `ElectronicWaybillAuthCommonService.judgeSdtAuth(oneOrgId, sysShopId)`：为 true 走 BSP，false 走丰门。
- **丰门链路** `OtoOpenFmCreateOrder:202`：构建 `FmCreateOrderRequest` → `handleRequest(EXTERNAL_WAYBILL_CREATE)` → `FmCommonService.fmApi` 调丰门 `external/waybill/create`；成功取 `waybillNo` + `childWaybillList`。
- **BSP 链路** `OtoOpenBspCreateOrder:667`：`BspOrderCreateService.service(CreateOrderCommonDto)`；寄付现结（BY_SHIPPER_CASH）被强制改为寄付 1（BSP 只支持 1/2/3 三种付款方式）。
- **幂等/防重**：两条链路都是「先向外部取号，拿到运单号后」才做本地查重：Redis 分布式锁 key `UNITED_STORE:OTO_ORDER_CREATE_LOCK_{运单号}:{appId}`（30s，`RedisKey.OTO_ORDER_CREATE_LOCK_KEY`）→ `us_fm_order` 按 `waybill_no` 查重 → 存在则回 `OtoOpenResponseVo.fail("-1","重复下单，运单号已存在")`。**注意：锁未获取时也走 fail("-1") 返回，不是 HTTP 异常**；`finally` 释放锁用的 key 是 `BATCH_ORDER_CREATE_LOCK_KEY`（与加锁 key 前缀不同，属既有缺陷，换号时锁不会释放，只能等 30s 过期）。
- **落库**：`us_fm_order`（主表，`status` 1 可用/2 删除）+ `us_fm_order_package_info` / `us_fm_order_trade_order` / `us_fm_order_logistics_service` / `us_fm_order_child_print_info`（见 `saveFmOrder:260`、`saveFmBspOrder:709`）。
- **前置校验**：组织必须有 `customerCode` 与 `checkCode`，否则「顾客编码,效验码没有配置」；收件信息必填；`gratuityFee` 若传必须 100~3000。
- **典型失败**：`appId非法` / `平台店铺id没有配置` / `月结卡号未验证` / `调用丰门接口报错:{msg}` / `重复下单，运单号已存在:{no}` / `没获取到运单号`（vm 外单返回空）。

### 1.2 cancelOrder（o2o 取消）
- `checkOtoOrder(mailNumber)`：`us_fm_order` 按 `waybill_no + status=1` 查，**查不到即「o2o运单号不存在或已取消」**（不可重复取消）。
- 按 `us_fm_order.order_source` 分流：丰门单 → `FmCancelOrder:1200` 调 `external/waybill/cancel`（返回体字符串 `"null"` 视为成功）；BSP 单 → `BspCancelOrder:1132` 组装 `BspOrderConfirmRequest`（dealType=2）调 `BspOrderConfirmService`，要求 `resStatus==2`，否则 `CANAL_ORDER_ORDER`(`US_200004`)「bsp取消订单返回不成功」。
- 成功后 `us_fm_order.status=2`（软删除，非物理删除）。

### 1.3 routeQuery（o2o 路由查询）
- **仅支持 BSP 查询**（源注释：丰门路由只支持抖店/拼多多，故不用）；`FmRouteQuery` 代码保留但注释掉了调用。
- 若运单号不在 `us_fm_order` 且未传 `phone` → 报「非o2o单子，phone必填」；若 phone 为空则从订单收件/寄件手机号截取**后四位**。
- 调用 `OrderRouteService.routeQuery(OrderRouteReq, false)`。

### 1.4 cloud/directOrder（o2o 插件打印）
- 先做参数校验 `checkOrderPrintHybridBatch:111`：`trackingOrder/childOrder/parentOrder` 至少一个为 "1"，否则 `PRINTING_ORDER_ARGUMENT_ERROR`(`US_1000005`)「请选择面单类型」；`mainNo` 不能为空且**不超过 10 条**。
- `cloudPrint` 逐条按 `waybill_no + status=1` 查 `us_fm_order`，任一不存在则整体报「以下运单号不存在:{list}」；母单/子单按 `subWaybillNo` 逗号拆分；`waybillNoCheckValue` 取收件手机号**后 6 位**。
- 组装 `SFCloudPrintVO`：模板由 `bizCode` 决定——空或 `130` 用 `oneLandQSYR*` 模板，`165` 用 `single165LandQSYR*`，其他报「暂不支持该模板编码」；`extJson` 按敏感信息开关动态拼接；`accessToken` 由 `getAccessToken:1967` 取顺丰开放平台 token（`partnerID/secret/grantType=password`，`apiResultCode` 必须 `A1000`，Redis `SF_AUTH_TOKEN` 缓存 `expiresIn` 秒）。
- **本接口不落库**，只返回打印报文与 token。

### 1.5 confirm（顺丰订单确认 json 版）
- `checkSign` + `monthlyCard` 非空时同样走月结卡号校验。
- 组织须有 customerCode/checkCode → `buildBspJsonParam`（`source` 空默认 1 通用下单；`source=2` 时须为 o2o 单，若原单 `order_source=1`(丰门) 则改为「A查B」三方单确认逻辑，用 `checkMonthlyCard`）→ `BspUpdateOrderService.confirm(dateJson, clientCode, checkWord)`。
- 结果判定：`apiResultData.success != TRUE` → `PARMAS_HAS_ERROR`「确认接口失败:{errorMsg}」；成功回 `resStatus/mailNumber/orderNumber`。

### 1.6 waybillintercepterCommon（O2O 拦截 / 理赔工单）
- `checkOtoOrder(wayBillNO)` 必须存在 → 写 `us_order_case_handle`（工单：雪花号、`work_order_type=1` 理赔、`source=2` API、`state=1` 待处理、`channel=SF_OTO`）+ `us_order_case_handle_log`（两条：API接口同步、工单类型说明）。
- `serviceCode` 必须是合法 `CaseTypeEnum`（1转寄/2退回/3优先派送/4再次派送/5改派自取点/6改派上门/7改派送时间/8改收件人/9改付款方式/10改代收…），否则「serviceCode不正确」。
- 最后 `PostStateService.doPostSync(req, caseNumber)` 同步到拦截服务。**无幂等**：同一运单重复调用会生成多张工单。

### 1.7 `/api/fm/waybill/getTemplate`（获取标准电子面单模板，FmController）
- 入口 `OS/controller/FmController.java:60`；实现 `OS/service/impl/FmServiceImpl.java:330`。
- 请求 `WaybillGetTemplateRequest extends FmCommonRequest`（`platformShopId` 必传 / `fmShopId` / `isCustomTemplate` / `customContent`）；响应 `WaybillGetTemplateResponse.templateDataList[]`（companyCode → templateList[templateId/templateCode/templateName/type/version/width/height/templateUrl/previewUrl]）。
- 流程：`platformShopId` 不能空 → `us_shop` by (platformShopId, appId) 取系统店铺（无则「平台店铺id没有配置」）→ 塞 `fmShopId = usShopDo.grantId` → `handleRequest(EXTERNAL_WAYBILL_GET_TEMPLATE)`（方法码 `external_waybill_getTemplate`，`FmApiMethodEnum:38`）。
- `handleRequest:264` 会从 JSON 中剔除 `appId/requestId/timestamp/sign/sysShopId` 后再组 `FmApiRequest{method,timestamp,oneOrgId,body}`；`flag=FAIL` 或 `code=FAIL` 抛 `BizException(fmApiResponse.code, message)`，空 body 抛 `SYS_ERR`「响应异常」。
- **无落库、无幂等**（纯查询转发）。

### 1.8 `/api/openNuts/monthly/createCode`（月结码生成，MonthlyCodeController）
- 入口 `OS/controller/MonthlyCodeController.java:27`；实现 `OS/service/impl/MonthlyCodeServiceImpl.java:74`。
- 请求 `CreateMonthlyCodeReq`(monthCard 必填 / timeout 默认 300s / needDynamicCode / mobile / remark)；响应 `CreateMonthlyCodeResp{success,errorCode,errorMessage,obj{uuid,dynamicCode}}`。
- 规则：`checkSign`；组织有 customerCode/checkCode；`monthCard` 必填；`timeout<=0` 报「失效时间必须大于0」；月结卡号须通过 `countCustomNumberListByOneOrgId`（同 1.1 开关逻辑）；**强制 `needDynamicCode=TRUE`**（第 75 行硬编码覆盖入参）。
- 外部：`restTemplateMonthlyBilling.postForObject(monthlyBillingConfig.url.createMonthCode, ...)` 调月结管家；解析 `CreateMonthCodeDynamicCodeResponseDTO{success,errorMessage,obj{uuid,dynamicCode}}`；成功后 `commonMonthlyBillingService.delayMonthCodeEffectCallBackSdj(...)`（延迟生效回调，带 userName=`sdj`/organizationId/organizationNumber/organizationCode）。
- 失败：动态码解析失败 → `SYS_ERR`「月结管家的月结码接口获取动态码失败」；RPC 异常 → `SYS_ERR`「...调用失败,稍后重试」；业务失败返回 `success=false` 但 **不抛异常**（HTTP 200）。

### 1.9 `/api/getThirdToken`（第三方 Token 获取，AuthController，**无类级前缀**）
- 入口 `OS/controller/AuthController.java:64` `getAuthToken`。
- 请求 `ThirdCustomerRequest`(source/userName/userId/timestamp，均为 RSA 密文；`userPhone/orgCode` 已注释)；响应：**裸 String token**（非 R 包装）。
- 流程：`us_third_customer_config.selectBySource(source)`（null → 「source非法」）→ `RSAUtil.decryptByPriKey(timestamp, priKey)` → 与服务器时间差 > ±180s 报「时间错误」→ 解密 userId/userName → `nutsUserFeign.findUserByAuthNameByManagerType(userName, applicationCode, "2")`（null → 「用户不存在」）→ 取 `organizationCode` → RestTemplate 请求 `{host}/zt/nuts-auth-core/wrapped/oauth/token?grant_type=password&client_id=nuts_area&client_secret=<硬编码在AuthController，已脱敏>&username=..&user_type=THIRD&orgCode=..&roleIds={roleId}`。
- 失败：响应空 → `NOT_LOGIN`「登录失败」；`errorCode != SUCCESS(0)` → 抛公共服务错误码与消息；成功取 `data.access_token`。
- 凭证表：`us_third_customer_config`（id/source/pubKey/priKey/roleId/url/status）。
- **注意**：`client_secret` 硬编码在代码中；`thirdCustomerConfigDo.getUrl()` 非空的分支只有一行 `todo 调用第三方客户验证客户信息` 日志，**实际未调用**。

---

## 2. 用户组织（NutsOrgUserSyncController，`@RequestMapping("/openNuts")`）

入口 `OS/controller/NutsOrgUserSyncController.java`；实现 `OS/service/impl/NutsOrgUserSyncServiceImpl.java`。

| # | 接口 | Controller | Service | 请求 DTO | 响应 |
|---|---|---|---|---|---|
| 10 | `/api/openNuts/userSync` | `:58` `userSync` | `:173` `syncUserInfoWithSwitch`（`:151` `syncUserInfo` 旧版保留） | `UserInfoReq`(id/authName/password/lastName/phone/sex/organizationId/isLeader/roleIds/positionName/isDelete/enable/superviseOrgIds/returnOnlyId) | `R` data = userId(Long) 或 `UserSyncResponseVO`，由 `returnOnlyId`（默认 true）决定 |
| 11 | `/api/openNuts/orgSync` | `:34` `createOrder`（方法名为历史遗留） | `:81` `syncOrgInfo` | `OrgInfoReq`(parentOrganizationCode/organizationCode*/organizationName*/address*/enable*/costCenterNumber/brand/contactName/phone/backupPhone/customNumber/codCardNo/storeType/returnOnlyId) | `R` data = orgId(Long) 或 `OrganizationAddVO` |

- **鉴权**：两者**都受 nacos 开关控制**（`NutsOrgUserSyncController.java:36-44`、`:60-68`）：`verifySign`（`NacosConfig:159` `${verifySign:true}`，默认 true）为 true 才走 `checkSign`；关闭后**完全不验签**，仅靠报文内 appId。
- **orgSync 前缀码**：先按 appId 查 `us_org_prefix`，无则 `getPrefix()` 随机生成 3 位字母（大小写去重）并插表；下游 `organizationCode = prefix + 入参organizationCode`，`parentOrganizationCode` 同理，同时把原值放入 `sourceOrganizationCode / sourceParentOrganizationCode`。
- **orgSync 外部调用**：`CommonOpenAPIToCommonService.sendToCommon({apiHost} + /zt/open-api/nuts-user-core/thirdOrganization/add, ...)`，使用 `commonAppKey/sKey/ivParameter` 做 AES 加密传输；异常抛 `PARMAS_HAS_ERROR`。
- **userSync 校验**（`checkParam:241`）：①先 `checkSuperviseOrgIds`（监管组织数 > 50 报错，每个 id 必须存在且属于当前 appId 组织树的本级/子级，去重后回写）；②有 `id` 视为编辑/删除，**跳过新增必填校验**；③新增校验 password/organizationId/authName/lastName/isLeader(0/1)/enable(0/1)/roleIds；④`organizationId` 组织必须存在，且其 `organizationNumber` 路径含 appId 或本身等于 appId，否则 `ILLEGAL_REQUEST`「该所属部门不属于当前组织的本级或子组织」。
- **userSync 外部调用**：`/zt/open-api/nuts-user-core/api/third/user`；返回 `jsonObject.data` 转 `UserSyncResponseVO`。
- **失败码**：`PARMAS_HAS_ERROR`(参数)、`ILLEGAL_REQUEST`(组织越权)、`SYS_ERR`(下游异常)。

---

## 3. 同城下单（OpenicController，`@RequestMapping("/tc")`）

入口 `OS/controller/OpenicController.java`；实现 `OS/service/impl/OpenicServiceImpl.java`（806 行）。全部 `checkOpenicSign`（appId→组织存在 + `us_open_config` + 同城签名）。
请求公共基类 `CityCommonReq`(shopId/appId/requestId/timestamp/sign)。

| # | 接口 | Controller | Service | 请求 DTO 关键字段 | 响应 DTO |
|---|---|---|---|---|---|
| 12 | `/api/tc/createOrder` | `:39` | `:142` `createOrder` | `CityCreateOrderReq`：shopType/shopOrderId/orderSource/lbsType/payType(1立即付2到付)/paymentType/orderTime/pushTime/isAppoint/expectTime/isInsured/declaredValue/gratuityFee(100~3000分)/returnFlag/receive{userName,userPhone,userAddress,userLng,userLat,cityName}/shop{shopName,shopPhone,shopAddress,shopLng,shopLat}/orderDetail{totalPrice,productType}/senderOrgCode | `CityCreateOrderResponse`(sdtOrderId/sfOrderId/sfBillId/shopOrderId/pushTime/totalPrice(分)/deliveryDistanceMeter/weightGram/startTime/expectTime/totalPayMoney/realPayMoney) |
| 13 | `/api/tc/queryOrderFlow` | `:56` | `:471` `listOrderFeed` | `CityListOrderFeedReq`(orderId/orderType/shopType/pushTime) | `CityListOrderFeedResponse`(sfOrderId/shopOrderId/createTime/pushTime/feed[]:operator/operatorName/operatorPhone/orderStatus/statusDesc) |
| 14 | `/api/tc/queryRiderLocation` | `:91` | `:541` `queryRiderLatestPosition` | `CityRiderLatestPositionReq`(orderId/orderType/shopType/pushTime) | `CityRiderLatestPositionResponse`(sfOrderId/shopOrderId/riderName/riderPhone/riderLng/riderLat/uploadTime) |
| 15 | `/api/tc/cancelOrder` | `:74` | `:496` `cancelOrder` | `CityCancelOrderReq`(orderId*/orderType*/shopType/cancelReason/pushTime) | `CityCancelOrderResponse`(sfOrderId/shopOrderId/pushTime) |
| 16 | `/api/tc/queryOrderStatus` **仅 uat 分支** | `feature/uat-branch-202608:.../OpenicController.java:110` | 同分支 `OpenicServiceImpl.java:650` | `CityGetOrderStatusReq`(orderId*/orderType/shopType；`orderType=2` 时 shopId 必填) | `CityGetOrderStatusResponse`(orderId/outOrderId/orderStatus/statusDesc/riderName/riderPhone/totalPrice/totalPayMoney/realPayMoney/couponsTotalFee/overflowFee/freeSendServiceFee/deductionFee/settlementType/deliveryDistanceMeter/weightGram/startTime/expectTime/pushTime/pickupCode/completeCode，金额单位**分**) |

### 3.1 createOrder 核心规则
- **同城服务配置校验**（前置）：①传 `senderOrgCode` → 转 orgId，`us_city_fast_send_conf` 按 (`shopId`, orgId) 精确匹配，不存在报「同城店铺ID与寄件组织编码不匹配」；②不传 → 仅按 `shopId` 查，命中 1 条才取 orgId，多条则 orgId 留空继续。
- **落库顺序**：先 `idWorkerService.getId()` 生成 `orderNo` → `ShortCodeKit.getShortCode()` 生成取货序号（周一零点起的秒数加密后 base32 + 当月日号，见 `ShortCodeKit.java:81`）→ **先插 `us_order`**（`insertAndGetId`）再调同城开放平台（源注释：「解决第三方API接口和数据库一致性问题」）。
- **外部调用**：`CityCreateOrderService.service(OpenicCreateOrderReqDTO)`；`shopOrderId` 为空自动填 `orderNo`；默认 `orderSource="shundiantong"`、`returnFlag=511`、`version=17`、productNum=1、pushTime/orderTime=当前秒级时间戳；注入 `openicConfig.devId/devKey`（顺丰同城开放平台凭证，非租户凭证）。
- **成功**：`errorCode==0` → `us_order.updateCityCreateOrderSuccess(orderNo, sfBillId, totalPrice/100)`（分转元）；插 `us_city_mail`（含 2026-10-20 新增 freeSendServiceFee/overflowFee/insureFee；gratuityFee 单独带时间戳）；插 `us_order_cargo`；发 `CreateOrderEventPublisher.publishCreateOrderEvent`（Kafka `HD_UNITED_STORE_CREATE_ORDER_GIS` + stream channel）。
- **失败**：上游 `errorCode!=0` 且 errorMsg 非空 → `CREATE_ORDER_ORDER`(`US_200005`)「下单失败:{上游msg}」；异常/空响应同样 `CREATE_ORDER_ORDER`。
- **幂等**：**代码未见**基于 `shopOrderId` 的查重（全仓无 `selectByShopOrderId`/`countByShopOrderId`）；重复调用会重复落 `us_order` 并向同城重复下单。

### 3.2 其余同城接口
- **queryOrderFlow / queryRiderLocation**：均为「构建上游请求 → 调同城 → MapStruct 映射回参」；上游 `errorCode` 非成功且 errorMsg 非空 → `SYS_ERR` 透传上游消息；其余异常也只记日志后丢到同一个 `SYS_ERR` 分支（**上游异常被吞、不区分「查不到」与「系统错」**）。
- **cancelOrder**：`us_city_mail.selectBySfOrderId(orderId)` 取 sdtOrderId（查不到「未查询到订单」）→ `us_order.queryByOrderNo`（查不到同）→ **状态机前置**：`orderStatus == null || >= ALREADY_PICK_PARK(2)` 报「取件后不可取消下单」→ 调同城取消 → 成功 `us_order.status = DELETE`（软删，不改 order_status）。
- **queryOrderStatus（uat）**：`buildGetOrderStatusReq` 校验 `orderType=2` 必须带 `shopId`（否则 `PARMAS_HAS_ERROR`「商家订单号查询时shopId不能为空」）；注入 `devId/devKey/pushTime`；上游异常 → `SYS_ERR`「查询订单实时信息异常，请稍后重试」；上游业务失败 → **透传上游 errorMsg**（如订单不存在、超 60 天）。

### 3.3 三个同城回调（接收端 `MG/controller/CityCallBackController.java`，`@RequestMapping("/external/cityCallBack")`）
- **无鉴权**（全类无 checkSign/token/filter 匹配；manager 仅对 `/api/bill/**` 挂 JWT 拦截器，`MG/config/InterceptorConfig.java:19`）。
- 负载类 `DeliverStatusChangeVO`（snake_case JSON：sf_order_id/shop_order_id/order_status/status_desc/push_time/sign/operator_name/operator_phone/ex_id/ex_content/cancel_reason/rider_lng/rider_lat）。
- 三者**靠不同 URL 区分**，不靠报文内字段：`/deliverStatusChange`(状态变更) / `/orderComplete`(完成，虽为独立 URL 但内部复用 `cityCallBackPush(STATE)`) / `/sfCancel`(顺丰原因取消) / `/riderException`(配送异常)；另有 `/syncCityCreateShopResult`(异步建店结果)。
- **必须返回** `{"error_code":0,"error_msg":"success"}`；任何异常捕获后返回 `{"error_code":-1,"error_msg":"error"}`（`CityCallBackController.java:38`、`:62` 等）。**注意：即使返回 error_code=-1 也是 HTTP 200**，上游是否会重推取决于其自身策略，代码内未做重试。
- 幂等/落库（`MG/service/impl/CityCallBackServiceImpl.java`）：
  - 公共：`cityMailDoMapper.selectBySfOrderId(sfOrderId)` 查 `us_city_mail.sf_order_id`，**查不到直接 return（视为已删/不关心，success 返回）**；不存在的回调不会报错。
  - `updateOrderStatus:114`：状态机 `order_status` 10→`us_order.order_status=1` ALREADY_CREATE_ORDER（+ 配送员姓名/手机加密写入 `us_city_mail`，`pickUpState=1`，pickup_time=push_time，发微信「已接单」，异步推汤丽柏奇）；12→`=2` ALREADY_PICK_PARK（异步 `sendShop(12)` → 收单中心 actionCode=110）；15→`=4` DISPATCH；其他仅 warn。**无版本号/时间戳比较，回调乱序会覆盖状态**。
  - `callOrderComplete:248`：`us_order.order_status=5` FINISH + sign_time=push_time；发微信「已签收」；`sendShop(17)` → actionCode=200。
  - `callSfCancel:236`：`us_order.status = DELETE`（软删，**不动 order_status**）。
  - `callBackRiderException:208`：`us_order.order_status=6` ABNORMAL；发微信「配送异常」（ex_id 映射中文，见 `CrossCityExceptionalEnum`）；不改 `status`。
  - 实际 SQL：`us_order` 按 `order_no` 更新 `order_status/pickup_time/sign_time/status/update_time`（`us_order` extend mapper `updateCityOrderStatus`，`limit 1`）。
- **转发分发**：`cityCallBackPush:96` 受 nacos `cityCallBackPush` 开关控制；开启时发 Spring 事件 → `CityCallBackEventListener` 按 STATE/EXCEPTION/SF_CANCEL 三个 stream channel 分发到二级消费（`MQ/stream/listener/openic/*`）。

---

## 4. 阿迪：`/open/adi/receiver/push`（**仅 uat 分支**，实际路径 `/api/open/adi/receiver/push`）

- 入口：`feature/uat-branch-202608:united-store-open-server/.../controller/AdiReceiverPushController.java:43`（类 `@RequestMapping("/open/adi/receiver")`，`extends AbstractController`）。
- 实现：`.../service/impl/AdiReceiverServiceImpl.java:40` `receive`。
- 请求 `AdiReceiverPushRequest extends RequestBaseInfo`（appId/requestId/timestamp/sign + orderNo*/receiverName*/phone*(RSA 密文)/province*/city*/district*/address*(RSA 密文)/zipCode/orderTime*）。
- **鉴权**：`checkSign`（四要素 + `us_open_config`）；`AdiReceiverPushController` 自行捕获 `BizException` → `R.error(HTTP 400, errorCode, msg)`，其他异常 → `R.error(HTTP 500, SYS_ERR, "处理异常，请稍后再试")`。**成功响应 data 为 `{"orderNo": "..."}`**。
- **处理顺序**（`receive`）：①业务必填校验 → ②**幂等** `us_adi_receiver_info.countByOrderNo(orderNo) > 0` 则直接返回 orderNo（**不覆盖原数据**，唯一键 `uk_order_no` 兜底）→ ③`adiReceiverRsaConfig.privateKey`（Nacos `adi.receiver.rsa.private-key`，`@RefreshScope` 热更新）为空报「服务端RSA私钥未配置」→ ④**RSA 分段解密** phone/address → ⑤组装 DO，`oneOrgId = 推送方 appId`。
- **分段解密**（`RSAUtil.decryptByPriKeySegment:84`，`united-store-common/.../utils/RSAUtil.java`）：PKCS8 私钥；**块大小 = 模长字节数（2048 位 = 256 字节）**，循环 `cipher.doFinal` 拼接 → UTF-8。即密文超过 245 字节（256-11，PKCS1 padding）时由发送方按块加密、此处按块解密。解密结果空 → 「{field} 解密结果为空」；异常 → 「{field} RSA解密失败」（均为 `PARMAS_HAS_ERROR`）。
- **落库**：`us_adi_receiver_info`（DDL `united-store-resource/sql/20261021_feature_v3.66.3_adi_receiver_info.sql`）；phone/address 字段带 `@CryptField`，**框架拦截器落库时自动加密**（代码写入明文）；`id` 由 `IdWorkerService` 生成（非自增）。
- **事务**：`@Transactional(rollbackFor = Exception.class)`。
- 典型失败：`orderNo/receiverName/phone/province/city/district/address 不能为空`、`orderTime 不能为空`、`RSA解密失败`、`服务端RSA私钥未配置`、签名/时间窗失败（`US_100003`）。

---

## 5. 推送（顺店通 → 客户）

### 5.1 清单运费推送（丰桥 `EXP_RECE_WAYBILLS_FEE_PUSH` 透传）
- **触发链路**：顺丰丰桥回调 `MG/controller/BspOrderBatchController.java:468` `POST /api/order/batch/feePush`（**无鉴权**，`FeePushRequest{content,sign}`，content 为丰桥原始报文）→ `BspOrderBatchServiceImpl.feePushKafka:8004` 发 Kafka `HD_UNITED_STORE_FEE_PUSH_TOPIC` → `MQ/.../FeePushSfKafkaListener.java:91` 一级消费：按 waybillNo 落 `us_bill_detail` / `us_bill_fee_detail`（按 feeTypeCode 先查后插/更）、更新 `us_order.freight/meterage_weight`、`us_order_extra`、一点一码折扣、运费额度管控扣减；若订单 oneOrgId 命中 `us_fee_push_org_config`（缓存 `FeePushOrgConfigCache` 5 分钟刷新，需 status=1 + pushUrl + appSecret 齐全）→ 转发二级 Kafka `HD_UNITED_STORE_WAYBILLS_FEE_PUSH`（`sendFeePushForwardMsg:339`）。
- **二级消费出口**：`MQ/.../WaybillsFeePushSfKafkaListener.java:89` `pushFee`：按 oneOrgId 取配置 → `fillSignInfo`（appId=一级组织ID、requestId=UUID、timestamp=毫秒、sign=MD5）→ 报文**业务字段原样透传、签名字段平铺在请求体**。
- **超时/重试**：初始 **3 次同步尝试，间隔 500ms**；RestTemplate 连接/读超时各 **5s**（`MQ/config/RestTemplateClient.java:48`）；可走丰声代理开关。响应判定：`code=200` 成功 / `code=400` 业务拒绝（不重试、只记 error 通知运维）/ 其他和非 JSON 均视为失败。
- **兜底重推**：3 次全失败写 `generic_sync_retry`（businessType=`WAYBILLS_FEE_PUSH`，businessId=orderId；同单号已有待重推记录则**更新刷新**不新增）→ Saturn Job `waybillsFeePushRetryJobHandler`（`united-store-job-executor`，建议 5~10 分钟一次）分批 100 条、**每条最多 3 次**、`last_retry_time < NOW()-1天` 才可重推；重推前 `refreshSign` 重新生成 requestId/timestamp/sign（原时间戳必然过期）；Job 末尾清理 90 天前记录。
- 典型失败：组织未配置/停用（静默放弃）、密钥空、签名窗口过期（客户侧拒绝）、客户 5s 内未响应。

### 5.2 店铺 ID/经纬度同步推送
- **生产端**：`MG/service/ShopIdSyncPushService.java:68` `push`；消费端 `MQ/.../ShopIdSyncPushSfKafkaListener.java:111`。Topic `HD_UNITED_STORE_SHOP_ID_PUSH`。
- **触发点**（均在 `MG/service/impl/CityFastSendConfServiceImpl` 维护动作成功后，推送异常不影响主流程）：批量导入店铺ID（新建行=add / 更新行=update，`:771`）、编辑店铺ID（`:798`）、经纬度设置（`:1178`）、批量开通/开通所有已覆盖（`:556` `pushAddIfEligible`，数据齐全推 add 首推）。
- **白名单**：nacos `shopIdPush.oneOrgIds`（逗号分隔一级组织ID，`MG/config/NacosConfig.java:382`），白名单外静默跳过；现仅 Maxmara 接入。
- **action 判定** `resolveAction:124`：按「店铺id 与经纬度是否齐全」求前后差——无→有=add、有→有=update、**无→无 或 半量数据=不推**；**无 delete**（页面无删除操作，配置行被删也不推）。前置还要求 `cover=1 且 enable=1`。
- **消费端**：nacos `shopIdPush.customerUrls` JSON 路由（key=一级组织ID → value=接收地址，`MQ/config/NacosConfig.java:164`），未配置不推；凭证 `us_open_config`（appId=oneOrgId）；报文 9 字段平铺 `{appId,requestId,timestamp,sign,action,orgCode,shopId,longitude,latitude}`（经纬度 WGS84，空值省略）。
- **重试**：与 5.1 同款（3 次 × 500ms、5s 超时、code=200/400 判定）；失败落 `generic_sync_retry`（businessType=`SHOP_ID_PUSH`，businessId=**一级组织ID**），**逐条插入不合并**（增量口径）；`shopIdPushRetryJobHandler` 隔日重推、最多 3 次；重推前 `refreshSign`。
- 典型失败：白名单未加 → 客户收不到（最常见）；`customerUrls` 无该 oneOrgId 路由；`us_open_config` 缺行或 appSecret 空；cover/enable 未开通；经纬度半量（只有 id 没坐标）。

---

## 6. 值得写进客户知识库的业务点

1. **同城订单状态码**：同城回调 `order_status` 1=订单创建、2=订单取消、10=配送员接单、12=配送员到店、15=配送中(已取货)、17=配送员完成；顺店通内部映射为 `us_order.order_status` 0=已导入/1=未收件/2=已取件/3=运输中/4=派送中/5=已签收/6=异常件，`status=2` 表示已删除（软删）。
2. **回调必须返回什么才算成功**：HTTP 200 + 响应体 `{"error_code":0,"error_msg":"success"}`；返回 `-1` 也是 HTTP 200，不会自动重推。回调**无签名校验**，以 `sf_order_id` 定位本地单。
3. **回调幂等性**：按 `sf_order_id` 查不到单即静默 return（返回 success）；**状态更新无版本/时间戳比较，乱序回调会覆盖状态**；重复回调会重复发微信/重复推收单中心（`sendShop`）——属已知风险。
4. **同城下单幂等**：`shopOrderId` 不传时系统自动用内部 `orderNo` 填充；**无 shopOrderId 查重**，重试下单会产生多单，请客户保证不重复调用或传稳定 `shopOrderId`。
5. **O2O 取号幂等**：以「运单号 + appId」查重，同一运单返回「重复下单」；并发时 30s 内会返回「O2O-电子面单通用取号中，请稍后」。
6. **同城取消限制**：`order_status >= 2`（已取件）后不可取消，接口报「取件后不可取消下单」。
7. **签名规则（通用）**：`MD5(sort(appId, requestId, timestamp, appSecret) 直接拼接)`，32 位小写；业务字段与 URL 不参与；timestamp 支持 10/13 位，±15 分钟窗口。**清单运费/店铺推送的签名由我方生成发给客户，客户按同规则验签**。
8. **RSA 分段**：阿迪推送 phone/address 用 RSA-2048 PKCS8 私钥按 256 字节块解密，明文超过 245 字节必须分段加密，否则解密失败。
9. **月结码**：`createCode` 强制返回动态码（`needDynamicCode` 入参被忽略）；默认 300s 有效；uuid 用于 `queryMonthlyWaybill` 查单；动态码生成失败返回 `success=false`（HTTP 200）而非报错。
10. **店铺经纬度为什么没收到**：依次检查 ①该一级组织是否在 nacos `shopIdPush.oneOrgIds` 白名单；②`shopIdPush.customerUrls` 是否配了接收地址；③同城服务是否 cover=1 且 enable=1；④是否店铺id 与经纬度**同时齐全**（半量不推）；⑤有无 delete 场景（页面无删除操作，删除不会推）；⑥查 mq-consumer 日志前缀 `ShopIdSyncPush`+requestId、重推日志前缀「店铺id经纬度重推」。
11. **清单运费推送为什么没收到**：①订单 oneOrgId 未在 `us_fee_push_org_config` 配置或 status≠1 或 pushUrl/appSecret 空；②客户响应非 `{"code":200}`；③code=400 会被判定业务拒绝不再重试；④查 `generic_sync_retry`（businessType=`WAYBILLS_FEE_PUSH`）与 Saturn Job 执行记录。
12. **错误码速查**：`US_100003`=参数异常/非法请求/签名失败、`US_100002`=操作失败(系统异常)、`US_100001`=系统繁忙、`US_200005`=下单失败、`US_200004`=取消订单失败、`US_1000005`=请选择面单类型、`US_100019`=获取二级组织不存在。

