encoding: utf-8
format: csv
hashing: md5
name: bgc_zoop_raw
path: schemas/BGC_Zoop_Raw.csv
profile: tabular-schemas-resource
notschema:
  fields:
    - name: SAMPLE
      type: integer
    - name: TAXON_NAME
      type: string
    - name: TAXON_GROUP
      type: string
    - name: TAXON_GRP01
      type: string
    - name: GENUS
      type: string
    - name: SPECIES
      type: string
    - name: SPCODE
      type: integer
    - name: ZOOP_ABUNDANCE_M3
      type: number
  primaryKey:
    - SAMPLE
    - TAXON_NAME
  missingValues:
    - ''
    - (null)
  version: 0.1.0
scheme: file
