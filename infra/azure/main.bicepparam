using './main.bicep'

param location = 'newzealandnorth'
param containerImage = 'ghcr.io/zeeekrom/rivulet-localops:v0.7.1'
param namePrefix = 'rivulet-demo'
param release = 'v0.7.1'
param expiresOn = '2026-10-24'
