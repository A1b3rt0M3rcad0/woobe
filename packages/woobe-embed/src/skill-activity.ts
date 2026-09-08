import { operationLabel } from '@woobe/runtime-client';
export interface SkillActivity {
  tool_name?: string;
  skill_name?: string;
  skill_version?: string;
  status?: string;
  success?: boolean | null;
  tool_call_id?: string;
  input?: unknown;
  output?: unknown;
}

export { isSkillOperation as isSkillActivity, skillActivityLabel } from '@woobe/runtime-client';

export function skillEvidenceLabel(activity: SkillActivity, named: boolean): string {
  const label = operationLabel(activity, named);
  const status = activity.status === "cancelled" || activity.status === "interrupted" ? activity.status
    : activity.success === false || activity.status === "error" || activity.status === "failed" ? "failed"
    : activity.status === "running" ? "running"
    : activity.success === true || activity.status === "success" ? "completed" : "requested";
  return `${label} · ${status}`;
}
