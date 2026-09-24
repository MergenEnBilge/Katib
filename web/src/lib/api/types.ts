import type { components } from './schema';

type S = components['schemas'];

export type Project = S['ProjectOut'];
export type ProjectClass = S['ClassOut'];
export type ImageItem = S['ImageOut'];
export type ImagePage = S['ImagePageOut'];
export type Annotation = S['AnnotationOut'];
export type Job = S['JobOut'];
export type FormatInfo = S['FormatOut'];
export type BatchOp = S['OpIn'];
export type OpResult = S['OpResultOut'];
export type ImageStatus = 'todo' | 'in_progress' | 'done' | 'approved' | 'rejected';
