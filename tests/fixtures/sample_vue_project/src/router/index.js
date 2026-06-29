import Vue from 'vue'
import Router from 'vue-router'
import Layout from '@/layout'

Vue.use(Router)

const routes = [
  {
    path: '/order',
    component: Layout,
    meta: { title: '订单管理' },
    children: [
      {
        path: 'list',
        name: 'OrderList',
        component: () => import('@/views/order/list'),
        meta: { title: '订单列表' }
      },
      {
        path: 'detail/:id',
        name: 'OrderDetail',
        component: () => import('@/views/order/detail'),
        meta: { title: '订单详情' }
      }
    ]
  },
  {
    path: '/user',
    name: 'User',
    component: () => import('@/views/user/index'),
    meta: { title: '用户管理' }
  }
]

export default new Router({ routes })
