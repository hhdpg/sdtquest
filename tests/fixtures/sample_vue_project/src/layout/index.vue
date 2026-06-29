<template>
  <div class="app-layout">
    <div class="sidebar">
      <el-menu :default-active="activeMenu">
        <el-menu-item index="/order/list">订单列表</el-menu-item>
        <el-menu-item index="/user">用户管理</el-menu-item>
      </el-menu>
    </div>
    <div class="main-container">
      <router-view />
    </div>
  </div>
</template>

<script>
export default {
  name: 'Layout',
  computed: {
    activeMenu() {
      return this.$route.path
    }
  }
}
</script>

<style scoped>
.app-layout { display: flex; height: 100vh; }
.sidebar { width: 200px; }
.main-container { flex: 1; padding: 20px; }
</style>
