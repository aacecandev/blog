{{- define "blog.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "blog.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "blog.labels" -}}
app.kubernetes.io/name: {{ include "blog.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Values.global.imageTag | default .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "blog.backendImage" -}}
{{- if .Values.backend.image.repository -}}
{{- printf "%s:%s" .Values.backend.image.repository (.Values.backend.image.tag | default "latest") -}}
{{- else -}}
{{- printf "%s/backend:%s" .Values.global.imageRegistry (.Values.backend.image.tag | default "latest") -}}
{{- end -}}
{{- end -}}

{{- define "blog.frontendImage" -}}
{{- if .Values.frontend.image.repository -}}
{{- printf "%s:%s" .Values.frontend.image.repository (.Values.frontend.image.tag | default "latest") -}}
{{- else -}}
{{- printf "%s/frontend:%s" .Values.global.imageRegistry (.Values.frontend.image.tag | default "latest") -}}
{{- end -}}
{{- end -}}
