<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
const rows = ref<any[]>([])
const err = ref('')
async function load() { rows.value = await api('/candidates') }
async function toggle(c: any) {
  err.value = ''
  try {
    await api(`/candidates/${c.id}`, { method: 'PATCH', body: JSON.stringify({ special: !c.special }) })
    await load()
  } catch (e: any) {
    err.value = `标记失败：${e.message}`
  }
}
onMounted(load)
</script>
<template>
  <h1>考生名册</h1>
  <p class="sub">夹板名册样式 · 特殊考生只坐前排名额格</p>
  <p v-if="err" class="hs-err">{{ err }}</p>
  <div class="hs-clipboard" style="max-width:460px">
    <h2>考生名册 · Clipboard</h2>
    <div v-for="r in rows" :key="r.id ?? JSON.stringify(r)" class="hs-roster-row">
      <div>
        <div>
          {{ r.name }}
          <span v-if="r.special" class="badge badge-warn">特</span>
        </div>
        <div class="hs-ticket">{{ r.ticket_no }}</div>
      </div>
      <div>
        卷{{ r.paper_id }} · 室{{ r.hall_id }}
        <button class="btn" style="padding:0.15rem 0.5rem;font-size:0.72rem;margin-left:0.4rem" @click="toggle(r)">
          {{ r.special ? '取消特殊' : '标为特殊' }}
        </button>
      </div>
    </div>
  </div>
</template>
