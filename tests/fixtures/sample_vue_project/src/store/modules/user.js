import { getUserInfo, getUserList } from '@/api/user'

const user = {
  namespaced: true,
  state: {
    currentUser: null,
    users: [],
    roles: []
  },
  actions: {
    async getInfo({ commit }) {
      const res = await getUserInfo()
      commit('SET_CURRENT_USER', res.data)
    },
    async fetchUsers({ commit }) {
      const res = await getUserList()
      commit('SET_USERS', res.data)
    }
  },
  mutations: {
    SET_CURRENT_USER(state, user) {
      state.currentUser = user
    },
    SET_USERS(state, users) {
      state.users = users
    }
  },
  getters: {
    currentUser: state => state.currentUser,
    userCount: state => state.users.length
  }
}

export default user
