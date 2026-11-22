import {api} from '../api.js';
import {badge, el, table, toast} from '../components.js';
import {field, form, money, select, title} from './shared.js';

const transferStatus={posted:['已入账','green'],reversed:['已冲回','neutral']};
const newKey=()=>window.crypto?.randomUUID?crypto.randomUUID():`key-${Date.now()}-${Math.random().toString(36).slice(2)}`;

function ledger(rows,user,refresh) {
  const t=el('table');
  t.append(el('thead',{},[el('tr',{},['时间','片区','转出月','接收月','金额','状态','经办','说明','操作'].map(h=>el('th',{text:h})))]));
  const body=el('tbody');
  if (!rows.length) body.append(el('tr',{},[el('td',{colSpan:9,class:'empty',text:'暂无转拨流水'})]));
  for (const row of rows) {
    const [text,kind]=transferStatus[row.status];
    const action=user.role==='analyst'&&row.status==='posted'
      ? el('button',{class:'button tiny',text:'冲回',onClick:async()=>{
          const note=window.prompt(`按原流水 #${row.id} 冲回 ${money(row.amount_cents)}，请填写冲回说明（至少5个字）`);
          if (note===null) return;
          if (note.trim().length<5) { toast('冲回说明至少5个字','error'); return; }
          try { await api(`/lease-desk/budget-transfers/${row.id}/reverse`,{method:'POST',body:JSON.stringify({note:note.trim()})}); toast('已按原流水冲回','success'); await refresh(); }
          catch(error) { toast(error.message,'error'); }
        }}) : null;
    body.append(el('tr',{},[
      el('td',{text:new Date(row.created_at).toLocaleString('zh-CN',{hour12:false})}),
      el('td',{text:row.neighborhood}),
      el('td',{text:row.from_month}),
      el('td',{text:row.to_month}),
      el('td',{text:money(row.amount_cents)}),
      el('td',{},[badge(text,kind)]),
      el('td',{text:row.created_by_name}),
      el('td',{text:row.status==='reversed'?`${row.note} ｜ 冲回：${row.reversal_note}`:row.note}),
      el('td',{},[action]),
    ]));
  }
  return el('div',{class:'table-wrap'},[t]);
}

export async function budgetPage(main,user,refresh) {
  const [{budgets,neighborhoods},{transfers}]=await Promise.all([api('/lease-desk/budgets'),api('/lease-desk/budget-transfers')]);
  main.append(title('片区让利预算','按新租期开始月份核算签约让利和当前有效报价承诺；同一片区内可在启租月之间转拨剩余额度。'));
  if (user.role==='analyst') {
    main.append(el('section',{class:'panel'},[form('设定让利额度',[
      select('neighborhood','房源片区',neighborhoods.map(item=>[item,item])),
      field('starts_month','启租月第一日',{type:'date'}),field('cap_cents','预算额度（分）',{type:'number',min:0,step:1}),
      field('justification','额度依据',{minlength:5}),
    ],'保存让利额度','/lease-desk/budgets',refresh,{method:'PUT'})]));
    const options=budgets.map(row=>[row.id,`${row.neighborhood} · ${row.starts_month} · 余额 ${money(row.remaining_cents)}`]);
    if (budgets.length>=2) main.append(el('section',{class:'panel'},[form('转拨两月剩余额度',[
      select('from_budget_id','转出预算月',options),
      select('to_budget_id','接收预算月',options),
      field('amount_cents','转拨金额（分）',{type:'number',min:1,step:1}),
      field('note','转拨说明',{minlength:5}),
      el('input',{type:'hidden',name:'idempotency_key',value:newKey()}),
    ],'保存转拨','/lease-desk/budget-transfers',refresh)]));
  }
  main.append(el('section',{class:'panel'},[table(['片区','启租月','预算额度','已承诺','余额','口径'],
    budgets.map(row=>[row.neighborhood,row.starts_month,money(row.cap_cents),money(row.committed_cents),money(row.remaining_cents),row.justification]))]));
  main.append(el('section',{class:'panel'},[el('h3',{text:'转拨流水'}),ledger(transfers,user,refresh)]));
}
