<template>
  <div class="user-container">
    <el-table :data="users">
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="email" label="邮箱" />
      <el-table-column prop="role" label="角色" />
    </el-table>
  </div>
</template>

<script>
export default {
  name: 'User',
  computed: {
    users() {
      return this.$store.state.user.users
    }
  },
  created() {
    this.$store.dispatch('user/fetchUsers')
  }
}
</script>
