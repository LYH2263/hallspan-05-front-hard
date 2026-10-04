<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const s = ref<any>({})
const ledger = ref<any[]>([])
onMounted(async () => {
  s.value = await api('/seating/stats?hall_id=1')
  ledger.value = await api('/seating/ledger?hall_id=1')
})
</script>
<template>
  <h1>统计</h1>
  <p class="sub">排座占用与违规汇总 · 前排占用与名额台账同一套数</p>
  <div class="card" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem">
    <div><div class="muted">已排座</div><div class="stat">{{ s.seated }}</div></div>
    <div><div class="muted">未排上</div><div class="stat">{{ s.unplaced }}</div></div>
    <div><div class="muted">违规数</div><div class="stat">{{ s.violations }}</div></div>
    <div><div class="muted">座位容量</div><div class="stat">{{ s.capacity }}</div></div>
    <div><div class="muted">前排行数</div><div class="stat">{{ s.front_row_rows }}</div></div>
    <div><div class="muted">名额格数</div><div class="stat">{{ s.quota_slots }}</div></div>
    <div><div class="muted">前排已耗名额</div><div class="stat">{{ s.front_row_occupied }}</div></div>
  </div>
  <div class="card">
    <h2 style="margin:0 0 0.5rem;font-size:0.95rem">前排名额台账</h2>
    <p v-if="!ledger.length" class="muted" style="margin:0">名额账已关闭或尚无排座记录。</p>
    <table v-else>
      <thead><tr><th>台账</th><th>方案</th><th>前排行数</th><th>名额格</th><th>名额已耗</th><th>时间</th></tr></thead>
      <tbody>
        <tr v-for="r in ledger" :key="r.id">
          <td>#{{ r.id }}</td>
          <td>方案 #{{ r.plan_id }}</td>
          <td>{{ r.front_row_rows }}</td>
          <td>{{ r.quota_slots }}</td>
          <td>{{ r.quota_used }}</td>
          <td>{{ r.created_at }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
