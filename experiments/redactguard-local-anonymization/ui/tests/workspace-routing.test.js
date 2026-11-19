import test from "node:test";
import assert from "node:assert/strict";
import { parseAppRoute, appRoutes } from "../src/routing.js";

test("the entry page opens the experiment library without selecting a mixed leaderboard",()=>{
 for(const path of ["/","/client","/client/experiments/"]){
  const route=parseAppRoute(path);
  assert.equal(route.page,"experiments");
  assert.equal(route.canonicalPath,appRoutes.clientExperiments);
 }
});

test("existing execution and document deep links remain reachable",()=>{
 assert.equal(parseAppRoute("/client/models").page,"models");
 assert.equal(parseAppRoute("/client/capabilities").page,"capabilities");
 assert.equal(parseAppRoute("/advanced/models").area,"advanced");
 const route=parseAppRoute(appRoutes.clientDetail("case/one.txt","qwen4"));
 assert.equal(route.page,"detail");
 assert.equal(route.params.documentName,"case/one.txt");
 assert.equal(route.params.model,"qwen4");
});
