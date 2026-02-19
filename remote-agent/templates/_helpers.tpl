{{- define "remote-agent.labels" -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "remote-agent.clusterName" -}}
{{ .Values.cluster.name | default "unknown" }}
{{- end -}}

{{- define "remote-agent.environment" -}}
{{ .Values.cluster.environment | default "unknown" }}
{{- end -}}
