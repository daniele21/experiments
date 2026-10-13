import { matrixMetric } from "./capabilityMatrix.js";
export function sortExecutiveRows(rows, sort, metric) {
 const copy=[...(rows??[])];
 if (!sort?.column) return copy;
 const locale=(a,b)=>String(a??"").localeCompare(String(b??""),"it",{numeric:true,sensitivity:"base"});
 return copy.sort((a,b)=>{
  if(sort.column==="model")return (sort.direction==="asc"?1:-1)*locale(a.modelId,b.modelId);
  const va=matrixMetric(a.cells?.[sort.column],metric),vb=matrixMetric(b.cells?.[sort.column],metric);
  if(va===null&&vb!==null)return 1;
  if(vb===null&&va!==null)return -1;
  if(va!==null&&vb!==null&&va!==vb)return sort.direction==="asc"?va-vb:vb-va;
  return locale(a.modelId,b.modelId);
 });
}
export function nextHeatmapSort(current,column,metric) {
 if(current?.column===column)return {column,direction:current.direction==="asc"?"desc":"asc"};
 return {column,direction:column==="model"||metric==="fp"?"asc":"desc"};
}
