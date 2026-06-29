import request from '@/utils/request'

export function getOrderList(params) {
  return request({
    url: '/api/orders',
    method: 'get',
    params
  })
}

export function createOrder(data) {
  return request({
    url: '/api/orders',
    method: 'post',
    data
  })
}

export function deleteOrder(id) {
  return request({
    url: `/api/orders/${id}`,
    method: 'delete'
  })
}

export function getOrderDetail(id) {
  return request({
    url: `/api/orders/${id}`,
    method: 'get'
  })
}

export function exportOrders(params) {
  return request({
    url: '/api/orders/export',
    method: 'get',
    params,
    responseType: 'blob'
  })
}
