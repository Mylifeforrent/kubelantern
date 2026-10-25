{{/* 固定资源名前缀：文档与验收脚本依赖这些名字，禁止随意改名。 */}}
{{- define "huntai.labels" -}}
app.kubernetes.io/part-of: huntai-sre
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "huntai.postgresHost" -}}huntai-postgres{{- end -}}
{{- define "huntai.redisHost" -}}huntai-redis{{- end -}}
{{- define "huntai.apiHost" -}}huntai-api{{- end -}}
