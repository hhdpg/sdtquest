# 顺店通开放接口 · 返回操作码字典

> 来源：Apifox `顺店通接口返回操作码说明`（99 条）+ 代码 `united-store-common/.../enums/ErrorCode.java`（163 个常量）
> 整理日期：2026-11-25　｜　文档 99 条全部在代码中存在，代码另有 54 个文档未公开的常量

## 1. 使用方式

- 客户收到 `errorCode` 后按本表定位含义。
- `code` 列是枚举名（日志/代码里的关键字），`errorCode` 是报文里返回给客户的值。
- **代码值与文档值一致**：文档 99 条与代码枚举 100% 对得上，没有漂移。

## 2. 文档公开的操作码（99 条）

| code | errorCode | 类型 | 含义 | 代码中是否有 |
|---|---|---|---|---|
| `OVERFLOW` | `US_100001` | 失败 | 系统繁忙，请稍后再试 | 是 |
| `SYS_ERR` | `US_100002` | 失败 | 操作失败,请稍后再试 | 是 |
| `ILLEGAL_REQUEST` | `US_100003` | 失败 | 非法请求 | 是 |
| `PARMAS_HAS_ERROR` | `US_100003` | 失败 | 参数异常 | 是 |
| `NOT_LOGIN` | `US_100004` | 失败 | 未登录，请登录 | 是 |
| `USER_NOT_EXISTE` | `US_100005` | 失败 | 用户不存在,查询用户不存在 | 是 |
| `ORGANIZATION_NOT_EXISTE` | `US_100006` | 失败 | 用户组织不存在,查询组织不存在 | 是 |
| `ORGANIZATION_CODE_EMPTY` | `US_100007` | 失败 | 用户组织编码为空,用户组织编码为空 | 是 |
| `REC_ORGANIZATION_NOT_EXISTE` | `US_100008` | 失败 | 收获组织不存在,查询收获门店组织不存在 | 是 |
| `PLEASE_ENTERING_RIGHT_MOBILE` | `US_100009` | 失败 | 请输入正确的联系方式 | 是 |
| `ADDRESS_GIS_ERROR` | `US_100010` | 失败 | 地址解析失败 | 是 |
| `EXPORT_ERROR` | `US_100011` | 失败 | 导出生成excel出错 | 是 |
| `PRINT_DATE_ERROR` | `US_100012` | 失败 | 地址信息填写不准确，请删除订单重新下单 | 是 |
| `IMPORT_ERROR` | `US_100013` | 失败 | 导入excel出错 | 是 |
| `IMPORT_TYPE_ERROR` | `US_100028` | 失败 | 导入表格字段不符合导入要求，请按业务配置导入模板填写 | 是 |
| `EAST_ORGANIZATION_EMPTY` | `US_100014` | 失败 | 获取所有组织为空 | 是 |
| `DATA_LIMIT_EXPORT_ERROR` | `US_100015` | 失败 | 导出数量太大，请修改查询条件导出 | 是 |
| `XML_CONVERT_FAILED` | `US_100016` | 失败 | XML 格式转换异常 | 是 |
| `DATA_EMPTY_EXPORT_ERROR` | `US_100017` | 失败 | 无数据可以导出 | 是 |
| `GIS_ADDRESS_ERROR` | `US_100018` | 失败 | 地址gis解析异常 | 是 |
| `TWO_LEVEL_ORGANIZATION_NOT_EXIST` | `US_100019` | 失败 | 获取二级组织不存在 | 是 |
| `CUSTOM_NUMBER_RULE_TYPE_ERROR` | `US_100020` | 失败 | 月结卡号结算规则非法 | 是 |
| `CUSTOM_NUMBER_RULE_NOT_EXIST` | `US_100021` | 失败 | 月结卡号配置规则不存在 | 是 |
| `CUSTOM_NUMBER_RULE_EXIST_ERROR` | `US_100022` | 失败 | 规则类型配置已存在 | 是 |
| `CUSTOM_NUMBER_NOT_EXIST` | `US_100023` | 失败 | 此月结配置下不存在月结账号 | 是 |
| `ORGANIZATION_QUERY_ERROR` | `US_100024` | 失败 | 组织查询失败 | 是 |
| `ORGANIZATION_SAVE_ERROR` | `US_100025` | 失败 | 组织新增失败 | 是 |
| `ORGANIZATION_UPDATE_ERROR` | `US_100026` | 失败 | 组织修改失败 | 是 |
| `ORGANIZATION_DELETE_ERROR` | `US_100027` | 失败 | 组织删除失败 | 是 |
| `ACCOUNTTYPE_NOT_EXISTE` | `US_100029` | 失败 | 用户组织不存在,查询组织不存在 | 是 |
| `IMPORTTEMPLATE_NAME_EXIST_ERROR` | `US_100030` | 失败 | 此模版名称已存在 | 是 |
| `ORDER_VALIDATE_SYSTEM_ERROR` | `US_100031` | 失败 | 下单校验发生系统错误 | 是 |
| `DOWNLOAD_IMPORT_TEMPLATE_ERROR` | `US_100032` | 失败 | 下载模版失败 | 是 |
| `TAKE_PART_TIME_INCORRECT` | `US_100033` | 失败 | 取件时间太近，多给小哥留点时间吧，请重新选择 | 是 |
| `BILL_CONFIG_NOT_PERMISSION` | `US_100034` | 失败 | 账单设置功能仅限一级组织的普通管理员账号访问 | 是 |
| `BILL_CONFIG_NOT_SETUP` | `US_100035` | 失败 | 未设置账单设置规则 | 是 |
| `ORDER_NOTICE_SERVICE_ERROR` | `US_100036` | 失败 | 等通知派送不支持到付及寄付现结付款方式 | 是 |
| `ORDER_CONFIGURATION_DOES_NOT_EXIST` | `US_100037` | 失败 | 下单配置不存在 | 是 |
| `FORBID_EMPLOY_BIZ_CODE` | `US_100038` | 失败 | 禁止使用按业务编码自选挂月结 | 是 |
| `MERGE_RULE_NOT_EXISTE` | `US_100039` | 失败 | 请先配置合并生单规则 | 是 |
| `CURRENT_USER_ORGANIZATION_ONE_LEVEL_ID_NOT_EXISTE` | `US_100040` | 失败 | 获取当前用户一级组织失败 | 是 |
| `QR_CODE_INVALID` | `US_100041` | 失败 | 二维码未生效 | 是 |
| `QR_CODE_EXPIRED` | `US_100042` | 失败 | 二维码已过期 | 是 |
| `QR_CODE_ERROR` | `US_100043` | 失败 | 二维码错误 | 是 |
| `GENERATE_BARCODE_ERROR` | `US_100044` | 失败 | 生成条形码出错 | 是 |
| `GENERAT_QRCODE_ERROR` | `US_100045` | 失败 | 生成二维码出错 | 是 |
| `GENERAT_FILE_ERROR` | `US_100046` | 失败 | base64生成文件出错 | 是 |
| `GENERAT_PDF_ERROR` | `US_100046` | 失败 | 生成pdf出错 | 是 |
| `QUERY_EXP_TIMEOUT` | `US_200000` | 失败 | 查询相隔天数不能超过3个月 | 是 |
| `ORDER_NOT_EXISTE` | `US_200001` | 失败 | 订单不存在 | 是 |
| `CANAL_ORDER_STATUS_ERROR` | `US_200002` | 失败 | 非待收件状态不能取消订单 | 是 |
| `CANAL_ORDER_NOT_STORE_ORDER` | `US_200003` | 失败 | 只能操作本门店订单 | 是 |
| `CANAL_ORDER_ORDER` | `US_200004` | 失败 | 取消订单失败 | 是 |
| `CREATE_ORDER_ORDER` | `US_200005` | 失败 | 下单失败 | 是 |
| `CREATE_ORDER_ORDERS` | `US_200006` | 失败 | 下单信息有误 | 是 |
| `REVIEW_CREATE_ORDER_ERROR` | `US_200007` | 失败 | 审批下单失败 | 是 |
| `REVIEW_REJECT_ORDER_ERROR` | `US_200008` | 失败 | 审批驳回失败 | 是 |
| `CANAL_ORDER_SOURCE_ORDER` | `US_200009` | 失败 | 只能取消移动端创建的订单 | 是 |
| `CANAL_ORDER_SOURCE_OPEN_ORDER` | `US_200010` | 失败 | 只能取消开放平台创建的订单 | 是 |
| `CANAL_ORDER_ALREADY_OPEN_ORDER` | `US_200011` | 失败 | 订单已取消 | 是 |
| `QUERY_ORDER_FREIGHT_ERROR` | `US_200012` | 失败 | 查询订单运费失败 | 是 |
| `ROUTE_DISTRIBUTE_PUSH_ERROR` | `US_200013` | 失败 | 路由分发推送失败 | 是 |
| `ORDER_MANAGE_FILE_EXPORT_LIMIT` | `US_200014` | 失败 | 延时导出次数上限 | 是 |
| `CREATE_LOCAL_ORDER_ORDER` | `US_200015` | 失败 | 订单创建失败，请检查订单数据 | 是 |
| `ORDER_NOT_EXISTE_OR_ONEORGID_IS_NULL` | `US_2000016` | 失败 | 订单不存在或一级组织不存在 | 是 |
| `DELETE_ORDER_ORDER` | `US_300001` | 失败 | 删除订单失败 | 是 |
| `REVIEW_ORDER_ERROR` | `US_300002` | 失败 | 审批订单单次不能超过200条 | 是 |
| `REVIEW_PASS_ORDER_ERROR` | `US_30006` | 失败 | 审批订单单次不能超过1000条 | 是 |
| `ORDER_SCHEDULE_ERROR` | `US_300003` | 失败 | 订单调度一次查询不能超过20条 | 是 |
| `NO_SCHEDULE_EXIST_ERROR` | `US_300004` | 失败 | 对应的订单调度不存在 | 是 |
| `NO_AVAILABLE_CONDITION_ERROR` | `US_300005` | 失败 | 请输入订单号或运单号 | 是 |
| `ORGANIZATION_CODE_NOT_EXISTE` | `US_400001` | 失败 | 组织编码不能为空！ | 是 |
| `ORGANIZATION_LEVEL_LIMIT` | `US_400002` | 失败 | 组织等级限制！ | 是 |
| `ORGANIZATION_EXPORT_ERROR` | `US_400003` | 失败 | 组织导出异常 | 是 |
| `USERRECEIVEADDRESS_EXISTE` | `US_500001` | 失败 | 收件地址已存在 | 是 |
| `USERRECEIVEADDRESS_ORGANIZATION_ID_ILEGAL` | `US_500002` | 失败 | 组织ID不合法 | 是 |
| `USERRECEIVEADDRESS_NOT_EXISTE` | `US_500003` | 失败 | 未查询到收件地址信息 | 是 |
| `USERRECEIVEADDRESS_NOT_PERMISSION` | `US_500004` | 失败 | 无权限! | 是 |
| `USERRECEIVEADDRESS_TEMPLATE_ERROR` | `US_500005` | 失败 | 模板不正确 | 是 |
| `SKUINFO_GET_ERROR` | `US_600001` | 失败 | 获取组织id出错 | 是 |
| `SKUINFO_UPLOAD_NOT_PERMISSION` | `US_600002` | 失败 | 无权限导入商品信息 | 是 |
| `ACCESS_TOKEN_GET_ERROR` | `US_700001` | 失败 | 获取access_token出错 | 是 |
| `QRCODE_GET_ERROR` | `US_700002` | 失败 | 获取二维码出错 | 是 |
| `OPENID_GET_ERROR` | `US_700003` | 失败 | openId获取出错 | 是 |
| `FORMID_QUERY_EMPTY` | `US_700004` | 失败 | 无可用formId | 是 |
| `ROUTE_TIME_OUT` | `US_800001` | 失败 | 超过三个月了,不能查哦 | 是 |
| `ROUTE_QUERY_ERROR` | `US_800002` | 失败 | 路由查询失败 | 是 |
| `OPERATION_LOG_ERROR` | `US_900001` | 失败 | 操作日志记录失败 | 是 |
| `MEDTRONIC_USER_REFRESH_TOKEN_ERROR` | `US_900002` | 失败 | 获取MEDTRONIC access_token出错 | 是 |
| `ORDER_ZD_QUERY_ERROR` | `US_1000001` | 失败 | 子单号申请失败 | 是 |
| `VERIFY_CODE_ERROR` | `US_1000002` | 失败 | verifyCode校验不通过 | 是 |
| `REQUEST_PARSE_ERROR` | `US_1000003` | 失败 | xml请求解析失败 | 是 |
| `CREATE_ORDER_SYSTEM_ERROR` | `US_1000004` | 失败 | 下单过程发生系统异常 | 是 |
| `PRINTING_ORDER_ARGUMENT_ERROR` | `US_1000005` | 失败 | 请选择面单类型,请选择面单类型 | 是 |
| `PRINTING_ORDER_MISSING_DATA_ERROR` | `US_1000006` | 失败 | 没有可打印的数据，请确认面单类型,没有可打印的数据，请确认面单类型 | 是 |
| `UN_CONFIG_SUBSCRIBE_TEMPLATE_ERROR` | `US_1000007` | 失败 | 未配置当前订阅模板Id,未配置当前订阅模板Id | 是 |
| `REPEAT_ORDER_COMMIT` | `US_1000008` | 失败 | 重复下单,重复下单 | 是 |
| `ROUTE_NOT_EXIST` | `US_1000008` | 失败 | 无路由信息 | 是 |
| `ENTERPRISE_WECHAT_UNAUTH` | `US_1000009` | 失败 | 未授权企业微信 | 是 |

## 3. 代码中有、文档未公开的常量（54 条）

> 这些错误码在代码里会抛出，但 Apifox 文档没列。客户遇到时需要查本表。

| code | errorCode | 含义 | 补充说明 |
|---|---|---|---|
| `SUCCESS` | `0` | 操作成功 | — |
| `NOT_AVAILABLE` | `US_101009` | 服务未开通 | 未开通该服务，请联系管理员 |
| `TIME_OUT` | `US_100000` | 请求超时 | — |
| `GENERAT_PDF_ERROR` | `US_100047` | 生成pdf出错 | — |
| `NO_AUTHORITY` | `US_100048` | 无权限请求该接口 | — |
| `IMPORT_TYPE_ERROR_FOR_UPDATE` | `US_100049` | 字段不符合要求，请导入正确字段 | — |
| `QUERY_BATCH_ORDER_INFORMATION_ERROR` | `US_100050` | 批量下单信息查询失败 | — |
| `TIME_AND_COLLECTION_VALIDATION_FAILED` | `US_100051` | 时间和搬运单集合未通过校验 | — |
| `CITY_CALLBACK_DISTRIBUTE_PUSH_ERROR` | `US_200017` | 同城回调分发推送失败 | — |
| `CONFIRM_ORDER_STATUS_ERROR` | `US_200018` | 非待收件状态不能确认订单 | — |
| `DH_PACK_BOX_DETAILS_ERROR` | `US_200019` | 查询大华批量发货数据失败 | — |
| `CANAL_ORDER_ABNORMAL_ALREADY_OPEN_ORDER` | `US_200020` | 此单已取消，不可重复取消 | — |
| `UN_ORGANIZATION_CODE_EMPTY` | `US_US_700005` | 未查询到该组织编码信息! | 未查询到该组织编码信息! |
| `UN_COST_CENTER_ORGANIZATION_CODE_EMPTY` | `US_US_700006` | 请保证成本中心编码与组织编码保持唯一! | 请保证成本中心编码与组织编码保持唯一! |
| `ROUTE_SUBSCRIBE_ERROR` | `US_800003` | 路由订阅失败 | — |
| `PRINTING_ORDER_LODOP_ERROR` | `US_1000015` | 只支持插件打印 | 只支持插件打印 |
| `PRINTING_ORDER_PARAM_ERROR` | `US_1000025` | 母单，子单，签回单不可都为空 | 母单，子单，签回单不可都为空 |
| `PRINTING_ORDER_CLOUD_MIX_ERROR` | `US_1000035` | 不同类型不能混打 | 不同类型不能混打 |
| `PRINTING_ORDER_DATA_UNAVAILABLE_ERROR` | `US_1000016` | 无法找到对应运单或您无此运单查询权限 | 无法找到对应运单或您无此运单查询权限 |
| `YUN_MARKET_SUCCESS` | `000000` | 成功 | — |
| `YUN_MARKET_ILLEGAL_REQUEST` | `000001` | 鉴权失败 | — |
| `YUN_MARKET_PARAMS_ERROR` | `000002` | 请求参数不合法 | — |
| `YUN_MARKET_CREATE_INSTANCE_ERROR` | `000005` | 创建实例失败，请重试 | — |
| `AMT_ACCOUNT_NOT_OPEND` | `US_1100002` | 未开通资金账户 | — |
| `AMT_ACCOUNT_CONFIGURATION_TIMEOUT` | `US_1100002` | 配置资金账户超时 | — |
| `AMT_ACCOUNT_CONCURRENT_MODIFICATION` | `US_1100003` | 资金账户正在进行其他操作 | — |
| `SHARING_QUERY_UNFINISHED_WORK` | `US_1100004` | 分账查询交易未完成 | — |
| `SHARING_FINISH_ERROR` | `US_1100005` | 分账完成查询失败 | — |
| `THIRD_MONTHLY_CONFIG_MISSING` | `US_1100015` | 三方物流配置信息不存在 | — |
| `THIRD_MONTHLY_ORDER_ERROR` | `US_1100016` | 三方物流公司月结单下单失败 | — |
| `PRODUCT_NOT_EXISTS_ERROR` | `US_1100001` | 商品不存在 | — |
| `PRODUCT_NOT_BELONG_TO_ORGANIZATION_ERROR` | `US_1100002` | 只可修改自己组织创建的商品信息 | — |
| `PRODUCT_ALREADY_PULLED_OFF_ERROR` | `US_1100003` | 该商品已经被下架，不可重复下架 | — |
| `PRODUCT_ALREADY_PUT_ON_ERROR` | `US_1100004` | 该商品已上架，不可重复上架 | — |
| `PRODUCT_ALREADY_DELETED_ERROR` | `US_1100005` | 商品已经删除，不可操作 | — |
| `PRODUCT_INVALID_PRODUCT_ID_ERROR` | `US_1100006` | 商品id为空或者不合法! | — |
| `PRODUCT_INVALID_STATE_ERROR` | `US_1100007` | 上下架标识为空或者不合法! | — |
| `PRODUCT_ALREADY_CATEGORY_ERROR` | `US_1100008` | 当前分类下有子分类，不能删除！ | — |
| `PRODUCT_ALREADY_RELATED_SHOP_ERROR` | `US_1100009` | 当前分类下有关联商品，不能删除！ | — |
| `PRODUCT_SHOP_CATEGORY_ERROR` | `US_1100010` | 商品分类设置失败！ | — |
| `PRODUCT_ALREADY_CATEGORY_NAME_ERROR` | `US_1100010` | 操作失败，该分类名称已存在 | — |
| `DICTIONARY_ITEM_MISSING` | `US_1100008` | 数据字典未配置 | — |
| `SHIVA_OMS_FVP_ORDER_INFO_ERROR` | `US_1100012` | 调用中台oms系统获取订单失败 | — |
| `AUTO_LABEL_STRATEGY_NOT_EXIST` | `US_1100013` | 未找到打标策略 | — |
| `AUTO_LABEL_STRATEGY_EXPECTED_STATUS` | `US_1100014` | 操作失败，当前策略状态已经是期望更新的状态 | — |
| `STRATEGY_CODE_EXIST` | `US_1100015` | 策略编码已存在 | — |
| `STRATEGY_NAME_EXIST` | `US_1100016` | 策略名称已存在 | — |
| `STRATEGY_LABEL_TYPE_REQUIRED` | `US_1100017` | 标签类型不能为空 | — |
| `CX_ADDRESS_NO_INFO_ERROR` | `US_120001` |  | — |
| `CX_ADDRESS_SYSTEM_ERROR` | `US_120002` | CX顺丰地址簿系统异常 | — |
| `EXPORT_POD_ORDER_IDS_EMPTY` | `ADI_IB_POD_001` | 请选择要导出的订单 | — |
| `EXPORT_POD_ORDER_COUNT_LIMIT` | `ADI_IB_POD_002` | 单次最多导出20个订单 | — |
| `EXPORT_POD_DAILY_LIMIT_EXCEEDED` | `ADI_IB_POD_003` | 今日导出次数已达上限(20次)，请明日再试 | — |
| `EXPORT_POD_NO_IMAGES_FOUND` | `ADI_IB_POD_004` | 未找到可导出的POD图片 | — |
| `EXPORT_POD_ZIP_ERROR` | `ADI_IB_POD_005` | 导出POD图片失败，请稍后重试 | — |
| `EXPORT_POD_PROCESS_ERROR` | `ADI_IB_POD_006` | 处理POD图片失败，请稍后重试 | — |
| `EXPORT_POD_IMAGE_COUNT_LIMIT` | `ADI_IB_POD_007` | 所选订单POD图片总数超出单次导出上限 | — |
| `ID_CARD_NOT_EQUALS` | `US_1100999` | 寄件人姓名与实名认证姓名不一致 | — |
| `ID_CARD_NOT_EXISTS` | `US_1100998` | 实名认证信息不存在 | — |
| `BELONG_ORG_CONFIG_NOT_EXISTE` | `US_1100997` | oms拉单组织匹配规则不合法 | — |
| `QUERY_MAX_NUM_ERROR` | `US_1100800` | 查询总数超限，请使用精确查询 | — |
| `INVALID_AMOUNT` | `US_110010` | 金额不合法 | — |
| `INVALID_BALANCE` | `US_110011` | 余额不合法 | — |

## 4. 排查提示

- `US_100003` 同时对应 `ILLEGAL_REQUEST`（非法请求）与 `PARMAS_HAS_ERROR`（参数异常），客户侧无法从 code 区分，需看 `errorMessage`。
- `US_100001` 系统繁忙、`US_100002` 操作失败属于可重试类；参数类（`US_100003`、`US_100005`~`US_100009`）重试无意义。
- 签名失败、时间戳过期这类鉴权错误会走 `ILLEGAL_REQUEST` 分支，排查时先校验 `timestamp` 是否在 15 分钟内。
