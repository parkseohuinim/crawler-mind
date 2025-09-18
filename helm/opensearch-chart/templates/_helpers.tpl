{{- define "opensearch.name" -}}
{{ .Chart.Name }}
{{- end }}

{{- define "opensearch.fullname" -}}
{{- if .Values.fullnameOverride }}
{{ .Values.fullnameOverride }}
{{- else }}
{{ .Release.Name }}-{{ .Chart.Name }}
{{- end }}
{{- end }}

