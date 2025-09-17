{{/*
Expand the name of the chart.
*/}}
{{- define "crawler-mind.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "crawler-mind.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "crawler-mind.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "crawler-mind.labels" -}}
helm.sh/chart: {{ include "crawler-mind.chart" . }}
{{ include "crawler-mind.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "crawler-mind.selectorLabels" -}}
app.kubernetes.io/name: {{ include "crawler-mind.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "crawler-mind.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "crawler-mind.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Frontend labels
*/}}
{{- define "crawler-mind.frontend.labels" -}}
{{ include "crawler-mind.labels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
Frontend selector labels
*/}}
{{- define "crawler-mind.frontend.selectorLabels" -}}
{{ include "crawler-mind.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
MCP Client labels
*/}}
{{- define "crawler-mind.mcpClient.labels" -}}
{{ include "crawler-mind.labels" . }}
app.kubernetes.io/component: mcp-client
{{- end }}

{{/*
MCP Client selector labels
*/}}
{{- define "crawler-mind.mcpClient.selectorLabels" -}}
{{ include "crawler-mind.selectorLabels" . }}
app.kubernetes.io/component: mcp-client
{{- end }}

{{/*
MCP Server labels
*/}}
{{- define "crawler-mind.mcpServer.labels" -}}
{{ include "crawler-mind.labels" . }}
app.kubernetes.io/component: mcp-server
{{- end }}

{{/*
MCP Server selector labels
*/}}
{{- define "crawler-mind.mcpServer.selectorLabels" -}}
{{ include "crawler-mind.selectorLabels" . }}
app.kubernetes.io/component: mcp-server
{{- end }}

{{/*
Qdrant labels
*/}}
{{- define "crawler-mind.qdrant.labels" -}}
{{ include "crawler-mind.labels" . }}
app.kubernetes.io/component: qdrant
{{- end }}

{{/*
Qdrant selector labels
*/}}
{{- define "crawler-mind.qdrant.selectorLabels" -}}
{{ include "crawler-mind.selectorLabels" . }}
app.kubernetes.io/component: qdrant
{{- end }}

{{/*
OpenSearch Dashboards labels
*/}}
{{- define "crawler-mind.opensearchDashboards.labels" -}}
{{ include "crawler-mind.labels" . }}
app.kubernetes.io/component: opensearch-dashboards
{{- end }}

{{/*
OpenSearch Dashboards selector labels
*/}}
{{- define "crawler-mind.opensearchDashboards.selectorLabels" -}}
{{ include "crawler-mind.selectorLabels" . }}
app.kubernetes.io/component: opensearch-dashboards
{{- end }}

{{/*
Image name helper
*/}}
{{- define "crawler-mind.image" -}}
{{- $registry := .Values.global.imageRegistry | default .Values.image.registry -}}
{{- $repository := .Values.image.repository -}}
{{- $tag := .Values.image.tag | default "dev" -}}
{{- if $registry -}}
{{- printf "%s/%s/%s:%s" $registry $repository .component $tag -}}
{{- else -}}
{{- printf "%s/%s:%s" $repository .component $tag -}}
{{- end -}}
{{- end }}

{{/*
Get the PostgreSQL secret name
*/}}
{{- define "crawler-mind.postgresql.secretName" -}}
{{- printf "%s-postgresql" (include "crawler-mind.fullname" .) -}}
{{- end }}

{{/*
Get the PostgreSQL database URL
*/}}
{{- define "crawler-mind.postgresql.databaseURL" -}}
{{- $host := printf "%s-postgresql" (include "crawler-mind.fullname" .) -}}
{{- $port := .Values.postgresql.service.port | default 5432 -}}
{{- $database := .Values.postgresql.auth.database -}}
{{- $username := .Values.postgresql.auth.username -}}
{{- printf "postgresql+asyncpg://%s:$(POSTGRES_PASSWORD)@%s:%d/%s" $username $host $port $database -}}
{{- end }}
