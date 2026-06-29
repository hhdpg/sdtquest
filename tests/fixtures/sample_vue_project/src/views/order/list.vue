<template>
  <div class="order-list-container">
    <!-- 搜索表单 -->
    <el-form :model="searchForm" inline>
      <el-form-item label="订单编号" prop="orderNo">
        <el-input v-model="searchForm.orderNo" placeholder="请输入订单编号" />
      </el-form-item>
      <el-form-item label="状态" prop="status">
        <el-select v-model="searchForm.status" placeholder="请选择状态">
          <el-option value="pending" label="待处理" />
          <el-option value="completed" label="已完成" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button @click="handleReset">重置</el-button>
      </el-form-item>
    </el-form>

    <!-- 操作按钮 -->
    <div class="action-bar">
      <el-button type="primary" @click="handleCreate" v-permission="['order:create']">
        新建订单
      </el-button>
      <el-button @click="handleExport">导出</el-button>
    </div>

    <!-- 订单列表 -->
    <el-table :data="tableData" v-loading="loading">
      <el-table-column prop="orderNo" label="订单编号" width="150" sortable />
      <el-table-column prop="customerName" label="客户名称" />
      <el-table-column prop="amount" label="金额" />
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作" width="200">
        <template slot-scope="scope">
          <el-button size="mini" @click="handleView(scope.row)">查看</el-button>
          <el-button size="mini" type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建订单弹窗 -->
    <el-dialog :visible.sync="createDialogVisible" title="新建订单">
      <el-form :model="createForm" :rules="createRules" ref="createFormRef">
        <el-form-item label="订单编号" prop="orderNo" required>
          <el-input v-model="createForm.orderNo" placeholder="请输入订单编号" />
        </el-form-item>
        <el-form-item label="客户名称" prop="customerName" required>
          <el-input v-model="createForm.customerName" placeholder="请输入客户名称" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input-number v-model="createForm.amount" :min="0" />
        </el-form-item>
      </el-form>
      <div slot="footer">
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreate">确定</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getOrderList, createOrder, deleteOrder, exportOrders } from '@/api/order'

export default {
  name: 'OrderList',
  data() {
    return {
      loading: false,
      searchForm: {
        orderNo: '',
        status: ''
      },
      tableData: [],
      createDialogVisible: false,
      createForm: {
        orderNo: '',
        customerName: '',
        amount: 0
      },
      createRules: {
        orderNo: [{ required: true, message: '请输入订单编号', trigger: 'blur' }],
        customerName: [{ required: true, message: '请输入客户名称', trigger: 'blur' }]
      }
    }
  },
  created() {
    this.loadData()
  },
  methods: {
    async loadData() {
      this.loading = true
      try {
        await this.$store.dispatch('order/fetchList', this.searchForm)
        this.tableData = this.$store.getters['order/orderList']
      } finally {
        this.loading = false
      }
    },
    handleSearch() {
      this.loadData()
    },
    handleReset() {
      this.searchForm = { orderNo: '', status: '' }
      this.loadData()
    },
    handleCreate() {
      this.createDialogVisible = true
    },
    async submitCreate() {
      await this.$store.dispatch('order/createOrder', this.createForm)
      this.createDialogVisible = false
      this.loadData()
    },
    async handleDelete(row) {
      await this.$store.dispatch('order/deleteOrder', row.id)
      this.loadData()
    },
    handleView(row) {
      this.$router.push(`/order/detail/${row.id}`)
    },
    async handleExport() {
      await exportOrders(this.searchForm)
    }
  }
}
</script>

<style scoped>
.order-list-container { padding: 20px; }
.action-bar { margin-bottom: 16px; }
</style>
