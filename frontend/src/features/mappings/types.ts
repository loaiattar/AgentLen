export interface MappingField {
  sourceField: string
  targetField: string
}

export interface Mapping {
  id: string
  name: string
  fields: MappingField[]
  createdAt: string
}

export interface CreateMappingInput {
  name: string
  fields: MappingField[]
}
