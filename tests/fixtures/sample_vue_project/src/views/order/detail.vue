<template>
  <div class="order-detail-container">
    <el-descriptions title="订单详情" :column="2" border>
      <el-descriptions-item label="订单编号">{{ detail.orderNo }}</el-descriptions-item>
      <el-descriptions-item label="客户名称">{{ detail.customerName }}</el-descriptions-item>
      <el-descriptions-item label="金额">{{ detail.amount }}</el-descriptions-item>
      <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
    </el-descriptions>

    <div class="action-bar">
      <el-button type="primary" @click="handleEdit">编辑</el-button>
      <el-button @click="goBack">返回</el-button>
    </div>
  </div>
</template>

<script>
import { getOrderDetail } from '@/api/order'

export default {
  name: 'OrderDetail',
  data() {
    return {
      detail: {}
    }
  },
  created() {
    this.loadDetail()
  },
  methods: {
    async loadDetail() {
      const id = this.$route.params.id
      const res = await getOrderDetail(id)
      this.detail = res.data
    },
    handleEdit() {
      this.$message.info('编辑功能')
    },
    goBack() {
      this.$router.push('/order/list')
    }
  }
}
</script>
