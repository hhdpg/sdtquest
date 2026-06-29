import request from '@/utils/request'

export function getUserInfo() {
  return request({
    url: '/api/user/info',
    method: 'get'
  })
}

export function getUserList(params) {
  return request({
    url: '/api/users',
    method: 'get',
    params
  })
}
