import type { Page } from '@playwright/test'
import { respond, now, project, productionAgent } from './control-plane'
import { credential, model, collection, tool, surface, apiKey } from './resource-data'
import { emptyUsage } from './design-gallery'

export const populatedUsage = {
  ...emptyUsage, data_through:now, from:'2026-05-21T12:00:00Z',to:now,bucket:'day',
  timeseries: [{bucket_start:'2026-06-20T00:00:00Z',agent_runs:2,direct_agent_runs:2,network_agent_runs:0,successful_agent_runs:1,failed_agent_runs:1,network_runs:0,successful_network_runs:0,failed_network_runs:0,known_cost_usd:.22,network_run_cost_usd:null,agent_cost_per_run:.11,network_cost_per_run:null,llm_calls:2,input_tokens:1000,output_tokens:500,priced_agent_runs:2,partial_cost_agent_runs:0,unpriced_agent_runs:0,runtime_requests:2,successful_requests:1,failed_requests:1,priced_requests:2,partial_cost_requests:0,unpriced_requests:0}],
  summary: { ...emptyUsage.summary, known_cost_usd:.22, failed_spend_usd:.08, cost_coverage_percent:100,
    agent_runs:2,direct_agent_runs:2,successful_agent_runs:1,failed_agent_runs:1,priced_agent_runs:2,agent_run_success_rate:50,
    cost_per_priced_agent_run:.11,median_agent_run_cost_usd:.11,p95_agent_run_cost_usd:.14,llm_calls:2,input_tokens:1000,output_tokens:500,
    runtime_requests:2,successful_requests:1,failed_requests:1,priced_requests:2,cost_per_priced_request:.11,tokens_per_request:750 },
  composition: { input_tokens:1000,output_tokens:500,embedding_tokens:0,tool_calls:0,vector_queries:0 },
  breakdown: [{key:productionAgent.id,label:productionAgent.name,known_cost_usd:.22,share_percent:100,agent_runs:2,network_runs:0,successful_agent_runs:1,llm_calls:2,input_tokens:1000,output_tokens:500,cost_per_priced_agent_run:.11,cost_coverage_percent:100,runtime_requests:2,successful_requests:1,cost_per_priced_request:.11}],
  data_quality: {...emptyUsage.data_quality,fully_priced_agent_runs:2,fully_priced_requests:2,aggregation_lag_seconds:0},
  top_executions: [
    {run_id:'run-completed',run_type:'agent',agent_id:productionAgent.id,agent_name:productionAgent.name,environment:'production',release_id:'selected-release',release_version:'1.2.0',provider:'custom',model:'review-model',status:'completed',llm_calls:1,input_tokens:600,output_tokens:300,tool_calls:0,agent_runs_count:1,duration_ms:1200,known_cost_usd:.14,cost_status:'priced',started_at:'2026-06-20T11:59:58.800Z'},
    {run_id:'run-failed',run_type:'agent',agent_id:productionAgent.id,agent_name:productionAgent.name,environment:'production',release_id:'selected-release',release_version:'1.2.0',provider:'custom',model:'review-model',status:'failed',llm_calls:1,input_tokens:400,output_tokens:200,tool_calls:0,agent_runs_count:1,duration_ms:800,known_cost_usd:.08,cost_status:'priced',started_at:'2026-06-20T11:59:59.200Z'},
  ],
}

export const runLedger={
  summary:{agent_runs:2,direct_agent_runs:2,network_agent_runs:0,network_runs:0,active_top_level_runs:0,failed_top_level_runs:1,top_level_runs:2,failure_rate_percent:50,p95_top_level_latency_ms:1200,avg_agent_runs_per_network_run:null},
  direct_agent_runs:populatedUsage.top_executions.map((run,index)=>({id:run.run_id,trace_id:`trace-${index}`,project_id:project.id,agent_id:productionAgent.id,agent_name:productionAgent.name,session_id:null,network_execution_id:null,network_invocation_id:null,parent_run_id:null,environment:'production',origin:'direct',status:run.status,input_message:'Find the support handbook entry.',usage:{input_tokens:run.input_tokens,output_tokens:run.output_tokens,total_tokens:run.input_tokens+run.output_tokens,cost_usd:run.known_cost_usd},result:run.status==='completed'?{output:'The handbook entry is available.'}:null,failure_code:run.status==='failed'?'provider_timeout':null,failure_detail:run.status==='failed'?'The provider did not respond before the timeout.':null,started_at:run.started_at,completed_at:now,created_at:now})),
  network_runs:[],
}

export async function installResources(page:Page) {
  await page.route('**/*',async route=>{
    const path=new URL(route.request().url()).pathname
    if(path==='/ai/credentials')return respond(route,[credential])
    if(path==='/ai/provider-models')return respond(route,[model])
    if(path==='/knowledge/collections')return respond(route,[collection])
    if(path===`/knowledge/collections/${collection.id}`)return respond(route,collection)
    if(path==='/tools/tools')return respond(route,[tool])
    if(path===`/tools/tools/${tool.id}`)return respond(route,tool)
    if(path==='/knowledge/documents')return respond(route,[{id:'document-demo',project_id:project.id,collection_id:collection.id,title:'Support handbook',file_name:'handbook.md',content_type:'text/markdown',size_bytes:1200,status:'indexed',created_at:now}])
    if(path===`/core/projects/${project.id}/api-keys`)return respond(route,[apiKey])
    if(path===`/chat-surfaces/projects/${project.id}`)return respond(route,[surface])
    if(path===`/chat-surfaces/${surface.id}`)return respond(route,surface)
    if(path===`/ai/projects/${project.id}/skills`)return respond(route,[{id:'skill-demo',project_id:project.id,name:'Support review',created_at:now,latest_version_id:'skill-version-demo',latest_version:'1.0.0',latest_description:'Review support answers against the handbook.',latest_required_tools:[],latest_estimated_instruction_units:120,latest_resource_count:0,latest_version_created_at:now,version_count:1}])
    if(path===`/metering/projects/${project.id}/usage`)return respond(route,populatedUsage)
    if(path===`/core/projects/${project.id}/runs`)return respond(route,runLedger)
    await route.fallback()
  })
}
