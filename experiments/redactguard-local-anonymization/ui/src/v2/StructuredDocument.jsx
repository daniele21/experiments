import { useMemo } from "react";
import "./structured-document.css";

// Format the canonical Markdown used for inference, never the original binary
// document. Split text on visible line boundaries but retain PII React nodes.
function splitLines(parts) {
  const lines=[[]];
  for (const part of parts) {
    if(part.kind==="pii"){lines.at(-1).push(part);continue;}
    const sections=part.text.split("\n");
    sections.forEach((section,index)=>{
      if(index>0)lines.push([]);
      if(section)lines.at(-1).push({...part,text:section,id:`${part.id}-${index}-${lines.length}`});
    });
  }
  return lines;
}
const printable = segments => segments.map(s => s.kind==="pii" ? "[PII]" : s.text).join("");
const isTableRow = segments => {const s=printable(segments).trim();return s.startsWith("|")&&s.includes("|",1)};
const isSeparator = segments => /^\s*\|?[\s:|\-]+\|\s*$/.test(printable(segments)) && /---+/.test(printable(segments));
function cellsFromLine(segments) {
 const cells=[[]];
 for(const part of segments){
  if(part.kind==="pii"){cells.at(-1).push(part);continue;}
  const splits=part.text.split("|");
  splits.forEach((text,index)=>{
   if(index>0)cells.push([]);
   if(text)cells.at(-1).push({...part,text,id:`${part.id}-cell-${index}`});
  });
 }
 // Markdown rows start/end with pipes; trim only empty edge cells.
 if(cells[0]?.length===0)cells.shift();
 if(cells.at(-1)?.length===0)cells.pop();
 return cells;
}
function toBlocks(lines){
 const blocks=[];
 let index=0;
 while(index<lines.length){
  const text=printable(lines[index]).trim();
  if(!text){index++;continue;}
  if(isTableRow(lines[index])){
   const rows=[];let header=false;
   while(index<lines.length&&(isTableRow(lines[index])||isSeparator(lines[index]))){
    if(isSeparator(lines[index]))header=true;
    else rows.push(cellsFromLine(lines[index]));
    index++;
   }
   blocks.push({type:"table",rows,header});continue;
  }
  if(/^#{1,3}\s/.test(text)){blocks.push({type:"heading",parts:lines[index++]});continue;}
  blocks.push({type:"line",parts:lines[index++]});
 }
 return blocks;
}
export default function StructuredDocument({parts,renderPart}){
 const blocks=useMemo(()=>toBlocks(splitLines(parts)),[parts]);
 const render=(parts,prefix)=>parts.map((part,index)=>renderPart(part,`${prefix}-${index}`));
 return <div className="rb2-structured">
  {blocks.map((block,i)=>{
   if(block.type==="table")return <div className="rb2-structured-table-scroll" key={i}><table>
    {block.header&&block.rows.length>0&&<thead><tr>{block.rows[0].map((cell,j)=><th key={j}>{render(cell,`th-${i}-${j}`)}</th>)}</tr></thead>}
    <tbody>{block.rows.slice(block.header?1:0).map((row,ri)=><tr key={ri}>{row.map((cell,ci)=><td key={ci}>{render(cell,`td-${i}-${ri}-${ci}`)}</td>)}</tr>)}</tbody>
   </table></div>;
   if(block.type==="heading")return <h3 key={i}>{render(block.parts,`h-${i}`)}</h3>;
   return <p key={i}>{render(block.parts,`line-${i}`)}</p>;
  })}
 </div>;
}
