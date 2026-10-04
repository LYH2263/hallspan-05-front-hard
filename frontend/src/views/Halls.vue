<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const edit = ref<Record<number, number>>({})
const err = ref('')
async function load() {
  rows.value = await api('/halls')
  const m: Record<number, number> = {}
  for (const r of rows.value) m[r.id] = r.front_row_rows ?? 0
  edit.value = m
}
async function save(r: any) {
  err.value = ''
  try {
    await api(`/halls/${r.id}`, { method: 'PATCH', body: JSON.stringify({ front_row_rows: edit.value[r.id] }) })
    await load()
  } catch (e: any) {
    err.value = `保存被拒绝：${e.message}`
  }
}
onMounted(load)
</script>
<template>
  <h1>考室</h1>
  <p class="sub">考室网格与最小曼哈顿间距 · 前排行数 0 表示关闭名额账</p>
  <p v-if="err" class="hs-err">{{ err }}</p>
  <div class="card">
    <table>
      <thead><tr><th>编码</th><th>名称</th><th>行</th><th>列</th><th>最小间距</th><th>前排行数</th><th></th></tr></thead>
      <tbody>
        <tr v-for="r in rows" :key="r.id ?? JSON.stringify(r)">
          <td>{{ r.code }}</td><td>{{ r.name }}</td><td>{{ r.rows }}</td><td>{{ r.cols }}</td><td>{{ r.min_manhattan }}</td>
          <td>
            <input type="number" min="0" :max="r.rows" v-model.number="edit[r.id]" style="width:4.5rem" />
          </td>
          <td><button class="btn" @click="save(r)">保存</button></td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
