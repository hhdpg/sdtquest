# 顺店通开放接口清单（对外 API Inventory）

> 来源：Apifox 共享文档 `https://xrvqulx2bm.apifox.cn/`（口令 `sdt`，项目 id `5462491`）
> 整理日期：2026-11-25　｜　共 62 篇文档，其中 **47 个对外接口**、15 篇非接口资料
> 代码基线：`eps-store-core-united-store-be` 分支 `feature/v3.68.5`

---

## 1. 通用约定

### 1.1 环境前缀

| 环境 | 地址前缀 |
|---|---|
| SIT（顺丰云测试） | `https://united-store-ms.sit.sf-express.com/zt/hd-united-store-openserver` |
| UAT | `https://united-store-uat-ms.sf-express.com/zt/hd-united-store-openserver` |
| PROD | `https://united-store-ms.sf-express.com/zt/hd-united-store-openserver` |

> 文档里各接口写的是 `/api/xxx`，完整地址 = 环境前缀 + `/api` + 接口路径（少数文档已写全路径，见第 5 节注意事项）。

### 1.2 公共鉴权参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `appId` | 是 | 顺丰分配的应用 ID，同时提供 `appSecret` |
| `requestId` | 是 | 每次请求唯一标识，建议 UUID |
| `timestamp` | 是 | 毫秒时间戳，**15 分钟内有效** |
| `sign` | 是 | 签名，见 1.3 |

### 1.3 签名算法

```
按字典升序排列 [appId, requestId, timestamp, appSecret] 四个字符串
→ 直接拼接（无分隔符）
→ MD5 取 32 位小写
```

`appSecret` **只参与签名计算，不出现在请求报文中**。

参考实现（文档原文 Java）：

```java
private static String sign(List<String> param) {
    Collections.sort(param);
    StringBuilder sb = new StringBuilder();
    for (String str : param) sb.append(str);
    return MD5Util.encrypt32(sb.toString());
}
```

### 1.4 其他通用点

- 请求格式绝大多数为 `POST` + `application/json`。
- 返回值统一为 `R` 包装（`success` / `errorCode` / `errorMessage` / `data`），操作码字典见第 4 节。
- 7 个「推送/回调」类接口没有固定地址，由客户提供接收 URL，方向是 **顺店通 → 客户**。

---

## 2. 接口清单（47 个）

> 「代码落点」列是本地 `feature/v3.68.5` 分支的 Controller 方法；标 ⚠️ 的只在 `feature/uat-branch-202608` 分支。

### 2.1 下单（11）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 1 | 统一下单 | POST | `/api/universal/createOrder` | `UniversalCreateOrderController.createOrder` |
| 2 | 统一下单-新（电力/店配） | POST | `/api/universal/electric/createOrder` | `UniversalCreateOrderController.createOrder` |
| 3 | 店配下单 V2 | POST | `/api/universal/electric/createOrderV2` | `UniversalCreateOrderController.createOrderV2` |
| 4 | 统一下单-轩尼诗 | POST | `/api/universal/createOrderXns` | `UniversalCreateOrderController.createOrderXns` |
| 5 | 顺丰预下单 | POST | `/api/preorder/times` | `PreOrderController.preorderTimes` |
| 6 | 顺丰订单确认 | POST | `/api/cancel/confirm` | `BspOrderConfirmController.orderConfirm` |
| 7 | 子单号申请 | POST | `/api/open/subWaybillNumber/apply` | `BspCreateOrderController.createOrder` |
| 8 | 取消订单 | POST | `/api/cancel/order` | `BspOrderConfirmController.cancelOrder` |
| 9 | 店配取消订单 | POST | `/api/cancel/orderV2` | `BspOrderConfirmController.cancelOrderV2` |
| 10 | 订单放行/退回 | POST | `/api/delivery/trigger` | `BspDeliverNoticeController.deliveryNotice` |
| 11 | 国补订单信息推送 | POST | 顺店通 → 客户 | `BspOrderBatchController.countrySubsidyPush`（出口） |

### 2.2 查询（8）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 12 | 时效查询 | POST | `/api/order/deliverTm` | `BspOrderSearchController.deliverTm` |
| 13 | 运单号合法性校验 | POST | `/api/wayBillNo/validate` | `BspValidateWayBillNoController.validateWayBillNo` |
| 14 | 清单运费查询 | POST | `/api/order/freight` | `BspOrderSearchController.orderFreight` |
| 15 | 地址解析 | POST | `/api/gis/adsp/addressIdentify` | `GisController.gisAdspAddressIdentify` |
| 16 | 全渠道-下单结果查询（付费） | POST | `/api/order/allChannelSearch` | `BspOrderSearchController` |
| 17 | 下单结果查询 | POST | `/api/order/search` | `BspOrderSearchController.orderSearch` |
| 18 | 调度信息查询 | POST | `/api/order/schedule` | `BspOrderSearchController.orderSchedule` |
| 19 | 月结付款码查单 | POST | `/api/openNuts/monthly/queryMonthlyWaybill` | `MonthlyCodeController.queryMonthlyWaybill` |

### 2.3 路由（5）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 20 | 路由查询 | POST | `/api/order/routeQuery` | `BspOrderSearchController.routeQuery` |
| 21 | 支持 CX/BSP 渠道路由查询 | POST | `/api/order/routeQuery/v2` | `BspOrderSearchController.routeQueryV2` |
| 22 | 全渠道-路由查询（付费） | POST | `/api/order/allChannelRouteQuery` | `BspOrderSearchController.allChannelRouteQuery` |
| 23 | 全渠道-路由查询（付费-新） | POST | `/api/order/allChannelRouteQuery/v2` | `BspOrderSearchController.allChannelRouteQueryNew` |
| 24 | 全渠道-标准路由推送 | POST | 顺店通 → 客户 | `RouteController` / manager 侧推客户 |

### 2.4 打印（1）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 25 | 云打印 | POST | `/api/fq/cloundPrint` | `FengmenController.cloundPrint` |

### 2.5 O2O（9）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 26 | 电子面单通用取号 | POST | `/api/oto/createOrder` | `OtoOpenController.createOrder` |
| 27 | O2O 取消 | POST | `/api/oto/cancel/order` | `OtoOpenController.cancelOrder` |
| 28 | O2O 路由查询 | POST | `/api/oto/order/routeQuery` | `OtoOpenController.routeQuery` |
| 29 | O2O 插件打印 | POST | `/api/oto/cloud/directOrder` | `OtoOpenController.cloudPrintOrder` |
| 30 | 顺丰订单确认（json） | POST | `/api/oto/confirm` | `OtoOpenController.confirm` |
| 31 | O2O 拦截 | POST | `/api/oto/waybillintercepterCommon` | `OtoOpenController.waybillintercepterCommon` |
| 32 | 获取标准电子面单模板 | POST | `/api/fm/waybill/getTemplate` | `FmController.waybillGetTemplate` |
| 33 | 月结码生成 | POST | `/api/openNuts/monthly/createCode` | `MonthlyCodeController.createMonthlyCode` |
| 34 | 第三方 Token 获取 | POST | `/api/getThirdToken` | `AuthController.getAuthToken` |

### 2.6 用户组织（2）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 35 | 用户同步 | POST | `/api/openNuts/userSync` | `NutsOrgUserSyncController.userSync` |
| 36 | 组织同步 | POST | `/api/openNuts/orgSync` | `NutsOrgUserSyncController.createOrder` |

### 2.7 同城下单（9）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 37 | 创建同城订单 | POST | `/api/tc/createOrder` | `OpenicController.createOrder` |
| 38 | 订单状态流查询 | POST | `/api/tc/queryOrderFlow` | `OpenicController.queryOrderFlow` |
| 39 | 获取配送员实时坐标 | POST | `/api/tc/queryRiderLocation` | `OpenicController.queryRiderLocation` |
| 40 | 取消同城订单 | POST | `/api/tc/cancelOrder` | `OpenicController.cancelOrder` |
| 41 | 订单实时信息查询 | POST | `/api/tc/queryOrderStatus` | ⚠️ `OpenicController.queryOrderStatus` |
| 42 | 订单状态回调 | POST | 顺店通 → 客户 | `CityCallBackController.deliverStatusChange`（接收端） |
| 43 | 顺丰原因取消回调 | POST | 顺店通 → 客户 | `CityCallBackController.sfCancel` |
| 44 | 订单异常回调 | POST | 顺店通 → 客户 | `CityCallBackController.riderException` |
| 45 | 店铺 ID/经纬度同步推送 | POST | 顺店通 → 客户 | `ShopIdSyncPushService`（生产端）+ mq-consumer（推送端） |

### 2.8 清单运费 / 阿迪（2）

| # | 接口 | 方法 | 路径 | 代码落点 |
|---|---|---|---|---|
| 46 | 清单运费推送 | POST | 顺店通 → 客户 | `MaxmaraFeePushSfKafkaListener`（`EXP_RECE_WAYBILLS_FEE_PUSH` 透传） |
| 47 | 推送收方信息（阿迪） | POST | `/open/adi/receiver/push` | ⚠️ `AdiReceiverPushController` / `AdiReceiverServiceImpl` |

---

## 3. 非接口资料（15 篇）

### 3.1 字典项（7）

费用类型、增值服务可选值明细、巴枪操作码与订单状态对应表、物流公司附录、支付方式明细说明、顺店通产品类型明细、顺店通接口返回操作码说明

### 3.2 必读说明（2）

- `[必读]接口签名算法前置说明` —— 本文件 1.2/1.3 节即由此整理
- `常见错误统计` —— 错误码分布

### 3.3 数据模型（6）

- `Pet` / `Category` / `Tag` —— Apifox 自带示例模型，**无业务含义，可忽略**
- 阿迪项目：`AdiReceiverPushRequest` / `PushResponse` / `ErrorResponse`

---

## 4. 返回操作码（待补全）

`顺店通接口返回操作码说明` 已抓取原文，整理进知识库时需与代码 `ErrorCode` 枚举对齐。见 `docs/openapi-error-codes.md`（待生成）。

---

## 5. 注意事项与坑

1. **路径前缀不一致**：用户同步/组织同步文档写的是含 `/zt/hd-united-store-openserver` 的全路径，其余接口写 `/api/xxx`。客户拼接时容易双前缀或漏 `/api`。
2. **统一下单 4 个变体不是版本迭代**：`createOrder`（标准）、`electric/createOrder`、`electric/createOrderV2`（店配）、`createOrderXns`（轩尼诗）面向不同客户/业态，需按客户归属确定用哪个。
3. **路由全渠道付费接口 v1/v2 并存**：`allChannelRouteQuery` 与 `/v2`，`/v2` 对应 `AllChannelRouteQueryNewServiceImpl`，接入前需确认客户开通的是哪条。
4. **7 个推送/回调无固定地址**：国补推送、标准路由推送、同城 3 个回调、清单运费推送、店铺经纬度推送，都需要客户先提供接收 URL 并在顺店通侧配置。
5. **同城 3 个回调共用同一地址**：文档明确「3 个回调需同一地址，可根据参数区分」，客户实现时要按参数分流而非按路径分流。
6. **两个接口不在当前基线分支**：`/api/tc/queryOrderStatus`、`/open/adi/receiver/push` 只在 `feature/uat-branch-202608`，本地 `feature/v3.68.5` 读不到，做代码溯源时需切分支。
7. **`Pet`/`Category`/`Tag` 是模板残留**：Apifox 项目初始化自带，出对外文档时建议删除以免客户误解。

---

## 6. 后续工作（知识库建设）

| 步骤 | 产出 | 状态 |
|---|---|---|
| 1 | 接口清单（本文件） | ✅ |
| 2 | 47 个接口的代码业务逻辑梳理 → `docs/openapi-business-logic.md`（含三份原始笔记 `docs/notes/`） | ✅ |
| 3 | 错误码字典（文档 × `ErrorCode` 枚举对齐）→ `docs/openapi-error-codes.md` | ✅ |
| 4 | 客户问答知识卡（YAML，按 `data/cards/sdt/` 格式，一卡一问，约 40 张） | 待办 |
| 5 | 建索引 + 回归评估（`scripts/build_index.py` → `validate_cards.py` → `eval_cards.py`） | 待办 |

---

## 附：文档抓取方法（复现用）

```bash
# 1. 用口令换 Cookie
curl -X POST https://api.apifox.cn/api/v1/published-projects-auth \
  -H "Content-Type: application/x-www-form-urlencoded;charset=UTF-8" \
  --data "id=5462491&password=sdt"
# 记下 Set-Cookie 里的 apiDocToken.5462491 与 apiDocToken.5462491.sig

# 2. 抓全站索引
curl -H "Cookie: apiDocToken.5462491=...; apiDocToken.5462491.sig=..." \
  https://xrvqulx2bm.apifox.cn/llms.txt

# 3. 任意文档：URL 后加 .md
curl -H "Cookie: ..." https://xrvqulx2bm.apifox.cn/7179816m0.md
```

> 坑：不带 Cookie 访问 `.md` 返回的仍是「需要密码」的 HTML，HTTP 状态码是 200，容易误判为成功。
> `?pwd=sdt` 只在浏览器端生效，curl 无效。
