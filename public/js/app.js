const $=id=>document.getElementById(id);let chart;
const U=JSON.parse(document.body.dataset.usuario);
const DEF_INS=[0,2,4,6],DEF_CLK=["08:00","10:00","12:00","14:00"];
function add(t="",g="",c=""){const ins=$("ins").checked,r=document.createElement("div");r.className="row";
r.innerHTML=`<input ${ins?'type="number" step="0.5" min="0"':'type="text" inputmode="numeric" maxlength="5" placeholder="hh:mm" oninput="mask(this,\'h\')"'} value="${t}"><input type=number min=10 max=800 value="${g}"><button type="button" class="pen${c?" on":""}" title="Observação" onclick="const o=this.parentNode.querySelector('.obs');o.hidden=!o.hidden;if(!o.hidden)o.focus()">✏️</button><button type="button" onclick="this.parentNode.remove()">✕</button><input type="text" class="obs" ${c?"":"hidden"} maxlength="200" placeholder="Observação (opcional), ex.: após convulsão" value="${c}" oninput="this.parentNode.querySelector('.pen').classList.toggle('on',this.value.trim()!=='')">`;$("rows").appendChild(r)}
function modo(){const ins=$("ins").checked,def=ins?DEF_INS:DEF_CLK;
 $("lblt").textContent=ins?"Horas após a insulina":"Horário da medição";
 const cur=[...$("rows").children],gs=cur.map(r=>r.children[1].value),cs=cur.map(r=>r.children[4].value),n=Math.max(4,gs.length);
 $("rows").innerHTML="";for(let i=0;i<n;i++)add(def[i]??"",gs[i]||"",cs[i]||"")}
modo();
async function analisar(){
 const ins=$("ins").checked;
 const rows=[...$("rows").children].map(r=>({a:r.children[0].value,g:r.children[1].value,c:r.children[4].value.trim()})).filter(x=>x.a!==""&&x.g!=="");
 if(!ins&&rows.some(x=>!/^([01]\d|2[0-3]):[0-5]\d$/.test(x.a)))return alert("Use horários válidos no formato 24h (ex.: 08:30).");
 let leituras;
 if(ins){leituras=rows.map(x=>({t:+x.a,g:+x.g,l:x.a,c:x.c}))}
 else{let prev=-1,off=0,base=null;
  leituras=rows.map(x=>{const[h,m]=x.a.split(":").map(Number);let min=h*60+m+off;
   if(prev>=0&&min<prev){off+=1440;min+=1440}prev=min;if(base===null)base=min;
   return{t:(min-base)/60,g:+x.g,l:x.a,c:x.c}})}
 const res=await fetch("/api/analisar",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({idade:$("idade").value,insulina:ins,leituras:leituras.map(x=>({t:x.t,g:x.g}))})});
 const d=await res.json();if(!res.ok)return alert(d.erro);
 if(ins)leituras.sort((a,b)=>a.t-b.t);
 const xs=leituras.map(p=>ins?p.t:p.l),f=d.faixa;
 if(chart)chart.destroy();
 chart=new Chart($("chart"),{type:"line",data:{labels:xs,datasets:[
  {label:"Mín",data:xs.map(_=>f.min),borderWidth:0,pointRadius:0,fill:false},
  {label:`Faixa ${f.min}–${f.max}`,data:xs.map(_=>f.max),borderWidth:0,pointRadius:0,fill:"-1",backgroundColor:"rgba(22,163,74,.13)"},
  {label:"Glicose",data:leituras.map(p=>p.g),borderColor:"#7c5cff",backgroundColor:"#7c5cff",tension:.35,borderWidth:3,pointRadius:leituras.map(p=>p.c?8:5),pointBackgroundColor:leituras.map(p=>p.c?"#f59e0b":"#7c5cff")}]},
  options:{plugins:{tooltip:{callbacks:{afterLabel:c=>c.datasetIndex===2&&leituras[c.dataIndex].c?"💬 "+leituras[c.dataIndex].c:""}},legend:{labels:{filter:i=>i.text!=="Mín"}}},scales:{x:{title:{display:true,text:ins?"Horas após a insulina":"Horário da medição"}},y:{title:{display:true,text:"mg/dL"},suggestedMin:0}}}});
 $("res").style.display="block";$("faixa").textContent=f.nome+` · ${f.min}–${f.max} mg/dL`;
 $("tit").textContent=d.titulo;$("txt").textContent=d.texto;
 $("alerts").innerHTML=d.alertas.map(a=>`<div class="alert">⚠️ ${a}</div>`).join("");
 const s=d.resumo;$("stats").innerHTML=[["Média",s.media],["Máxima",s.maxima],["Mínima (nadir)",s.minima],["Na faixa",s.no_alvo+"%"]].map(([k,v])=>`<div class="stat"><b>${v}</b><span>${k}</span></div>`).join("");
 $("obs").innerHTML=leituras.filter(p=>p.c).map(p=>`<div class="obsitem"><b>${esc(p.l)}${ins?" h":""}</b> · ${p.g} mg/dL — 💬 ${esc(p.c)}</div>`).join("");
 $("conf").textContent=`Confiança do modelo: ${d.confianca}%`;ultima={rows,titulo:d.titulo,classe:d.classe,resumo:d.resumo,snap:{idade:$("idade").value,data:$("data").value,ins,faixa:`${d.faixa.nome} · ${d.faixa.min}–${d.faixa.max} mg/dL`,texto:d.texto,alertas:d.alertas,leit:leituras}}}
function mask(el,t){let v=el.value.replace(/\D/g,"");
 v=t==="d"?v.slice(0,8).replace(/^(\d{2})(\d)/,"$1/$2").replace(/^(\d{2}\/\d{2})(\d)/,"$1/$2"):v.slice(0,4).replace(/^(\d{2})(\d)/,"$1:$2");el.value=v}
const isoToBr=d=>d.split("-").reverse().join("/"),brToIso=d=>d.split("/").reverse().join("-");
function dataOk(d){const m=d.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);if(!m)return false;const x=new Date(+m[3],m[2]-1,+m[1]);return x.getMonth()==m[2]-1&&x.getDate()==+m[1]}
const esc=s=>s.replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let ultima=null;$("data").value=new Date().toLocaleDateString("pt-BR");
async function api(u,o={}){const r=await fetch(u,{...o,headers:{"Content-Type":"application/json"}});if(r.status===401)location.reload();return r}
async function salvar(){if(!ultima)return;if(!dataOk($("data").value))return alert("Use uma data válida no formato dd/mm/aaaa.");
 const r=await api("/api/medicoes",{method:"POST",body:JSON.stringify({data:brToIso($("data").value),idade:$("idade").value,insulina:$("ins").checked,...ultima})});
 if(!r.ok)return alert((await r.json()).erro||"Erro ao salvar");hist()}
async function hist(){const r=await api("/api/medicoes");if(!r.ok){$("hist").textContent="Não foi possível carregar o histórico.";return}
 const L=window._L=await r.json();
 $("hist").innerHTML=L.length?L.map(m=>`<div class="item"><div><b>${m.data.split("-").reverse().join("/")}</b> · ${m.idade} ano(s) · ${m.insulina?"com":"sem"} insulina<br><small style="color:var(--mut)">${m.titulo} · média ${Math.round(m.resumo.media)} mg/dL</small>${m.rows.filter(x=>x.c).map(x=>`<small class="nota">💬 ${x.a}${m.insulina?" h":""} – ${x.c}</small>`).join("")}</div><div><button class="mini" onclick="abrir('${m.id}')">Abrir</button><button class="mini" onclick="excluir('${m.id}')">✕</button></div></div>`).join(""):'<small style="color:var(--mut)">Nenhuma medição salva ainda.</small>'}
function abrir(id){const m=window._L.find(x=>x.id===id);$("idade").value=m.idade;$("data").value=isoToBr(m.data);$("ins").checked=m.insulina;modo();$("rows").innerHTML="";m.rows.forEach(x=>add(x.a,x.g,x.c));analisar()}
async function excluir(id){if(!confirm("Excluir esta medição?"))return;await api("/api/medicoes/"+id,{method:"DELETE"});hist()}
let modoAuth="entrar";
function tab(m){modoAuth=m;$("tabE").classList.toggle("on",m==="entrar");$("tabC").classList.toggle("on",m==="criar");
 $("btnAuth").textContent=m==="entrar"?"Entrar":"Criar conta";$("s").autocomplete=m==="entrar"?"current-password":"new-password";
 $("s").placeholder=m==="criar"?"mínimo 8 caracteres":"";$("autherr").hidden=true}
async function auth(){const r=await fetch(modoAuth==="entrar"?"/api/login":"/api/cadastro",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({usuario:$("u").value,senha:$("s").value})});
 const d=await r.json();if(!r.ok){$("autherr").textContent=d.erro;$("autherr").hidden=false;return}location.reload()}
async function sair(){await fetch("/api/logout",{method:"POST"});location.reload()}
function abrirAuth(){$("auth").hidden=!$("auth").hidden;if(!$("auth").hidden)$("u").focus()}
if(U){$("quem").textContent="👤 "+U;$("btnWho").textContent="Sair";$("btnWho").onclick=sair;$("btnSalvar").hidden=false;$("histCard").hidden=false;hist()}
else{$("quem").textContent="Modo visitante · nada é salvo";$("btnWho").textContent="Entrar / Criar conta";$("btnWho").onclick=abrirAuth;$("dicaGuest").hidden=false}

function salvarPng(c,nome){const a=document.createElement("a");a.href=c.toDataURL("image/png");a.download=nome;a.click()}
function baixarGrafico(){if(!chart)return alert("Analise a curva primeiro.");const s=chart.canvas,c=document.createElement("canvas");c.width=s.width;c.height=s.height;
 const x=c.getContext("2d");x.fillStyle="#fff";x.fillRect(0,0,c.width,c.height);x.drawImage(s,0,0);salvarPng(c,"curva-glicemica.png")}
function baixarResultado(){if(!chart||!ultima)return alert("Analise a curva primeiro.");
 const W=900,P=40,s=chart.canvas,ch=Math.round(s.height*(W-2*P)/s.width),e=ultima,n=e.snap,r=e.resumo,ob=n.leit.filter(p=>p.c);
 const c=document.createElement("canvas");c.width=W;c.height=3000;const x=c.getContext("2d");x.fillStyle="#fff";x.fillRect(0,0,W,3000);
 const q=(t,m)=>{const o=[];let l="";for(const w of t.split(" ")){if(x.measureText(l+w).width>m&&l){o.push(l.trim());l=""}l+=w+" "}o.push(l.trim());return o};
 let y=P;const t=(txt,f,col,lh)=>{x.font=f;x.fillStyle=col;for(const l of q(txt,W-2*P)){y+=lh;x.fillText(l,P,y)}y+=6};
 t("Curva Glicêmica Felina","bold 30px sans-serif","#5b3df5",36);
 t(`${n.data} · ${n.idade} ano(s) · ${n.ins?"com":"sem"} insulina`,"18px sans-serif","#555",26);
 t(`Faixa de referência: ${n.faixa}`,"18px sans-serif","#555",26);y+=10;
 x.drawImage(s,P,y,W-2*P,ch);y+=ch+20;
 t(e.titulo,"bold 24px sans-serif","#222",32);t(n.texto,"18px sans-serif","#444",26);
 n.alertas.forEach(a=>t("⚠ "+a,"bold 18px sans-serif","#dc2626",26));y+=6;
 t(`Média ${r.media} · Máxima ${r.maxima} · Mínima ${r.minima} mg/dL · ${r.no_alvo}% na faixa`,"bold 18px sans-serif","#222",26);
 if(ob.length){y+=10;t("Observações","bold 18px sans-serif","#222",26);ob.forEach(p=>t(`${p.l}${n.ins?" h":""} · ${p.g} mg/dL — ${p.c}`,"17px sans-serif","#444",24))}
 y+=14;t("Ferramenta educativa. Não substitui avaliação veterinária.","14px sans-serif","#888",20);
 const f=document.createElement("canvas");f.width=W;f.height=Math.min(y+P,3000);f.getContext("2d").drawImage(c,0,0);salvarPng(f,"resultado-curva-glicemica.png")}
