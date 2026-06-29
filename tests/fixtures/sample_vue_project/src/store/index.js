import Vue from 'vue'
import Vuex from 'vuex'
import order from './modules/order'
import user from './modules/user'

Vue.use(Vuex)

export default new Vuex.Store({
  modules: {
    order,
    user
  }
})
