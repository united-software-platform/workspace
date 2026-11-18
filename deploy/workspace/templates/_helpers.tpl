{{/*
Имя чарта, обрезанное до лимита DNS-имени в 63 символа.
*/}}
{{- define "workspace.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Полное имя: имя релиза, обрезанное до 63 символов.
*/}}
{{- define "workspace.fullname" -}}
{{- printf "%s" .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Общие метки ресурса.
*/}}
{{- define "workspace.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "workspace.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Селекторные метки ресурса.
*/}}
{{- define "workspace.selectorLabels" -}}
app.kubernetes.io/name: {{ include "workspace.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
