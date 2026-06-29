import { getOrderList, createOrder, deleteOrder } from '@/api/order'

const order = {
  namespaced: true,
  state: {
    list: [],
    detail: null,
    loading: false,
    total: 0
  },
  actions: {
    async fetchList({ commit }, params) {
      commit('SET_LOADING', true)
      const res = await getOrderList(params)
      commit('SET_LIST', res.data)
      commit('SET_LOADING', false)
    },
    async createOrder({ commit }, data) {
      await createOrder(data)
    },
    async deleteOrder({ commit }, id) {
      await deleteOrder(id)
    }
  },
  mutations: {
    SET_LIST(state, list) {
      state.list = list
    },
    SET_LOADING(state, loading) {
      state.loading = loading
    },
    SET_DETAIL(state, detail) {
      state.detail = detail
    }
  },
  getters: {
    orderList: state => state.list,
    isLoading: state => state.loading
  }
}

export default order
