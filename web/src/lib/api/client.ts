import type {
  Annotation,
  AttrDef,
  BatchOp,
  ClassOp,
  FormatInfo,
  Health,
  ImageItem,
  ImagePage,
  Job,
  OperationInfo,
  OpResult,
  Project,
  ProjectClass,
  RevertResult,
  ShapeItem,
} from './types';

const BASE = '/api/v1';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

interface ErrorBody {
  code?: string;
  message?: string;
  details?: Record<string, unknown>;
}

async function fail(response: Response): Promise<never> {
  const data = (await response.json().catch(() => null)) as ErrorBody | null;
  throw new ApiError(
    response.status,
    data?.code ?? 'error',
    data?.message ?? `The server answered ${response.status}.`,
    data?.details,
  );
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(BASE + path, init);
  } catch {
    throw new ApiError(0, 'network', 'Could not reach the Katib server. Check that it is running.');
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await send(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) return fail(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const q = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') q.set(key, String(value));
  }
  const text = q.toString();
  return text ? `?${text}` : '';
}

export interface ImageFilter {
  status?: string;
  q?: string;
  class_id?: string;
  has_annotations?: boolean;
  after?: string | null;
  limit?: number;
}

export const api = {
  formats: () => request<FormatInfo[]>('GET', '/formats'),

  projects: {
    list: (q?: string) => request<Project[]>('GET', `/projects${query({ q })}`),
    get: (id: string) => request<Project>('GET', `/projects/${id}`),
    create: (name: string) => request<Project>('POST', '/projects', { name }),
    rename: (id: string, name: string) => request<Project>('PATCH', `/projects/${id}`, { name }),
    remove: (id: string) => request<void>('DELETE', `/projects/${id}`),
  },

  classes: {
    list: (projectId: string) => request<ProjectClass[]>('GET', `/projects/${projectId}/classes`),
    create: (projectId: string, name: string, color?: string) =>
      request<ProjectClass>('POST', `/projects/${projectId}/classes`, { name, color }),
    update: (id: string, patch: { name?: string; color?: string; attr_schema?: AttrDef[] }) =>
      request<ProjectClass>('PATCH', `/classes/${id}`, patch),
    reorder: (projectId: string, ids: string[]) =>
      request<void>('POST', `/projects/${projectId}/classes:reorder`, { class_ids: ids }),
    merge: (id: string, targetId: string, dryRun: boolean) =>
      request<ClassOp>('POST', `/classes/${id}:merge`, { target_id: targetId, dry_run: dryRun }),
    remove: (id: string, dryRun: boolean) =>
      request<ClassOp>('POST', `/classes/${id}:delete`, { dry_run: dryRun }),
  },

  operations: {
    list: (projectId: string) =>
      request<OperationInfo[]>('GET', `/projects/${projectId}/operations`),
    revert: (id: string) => request<RevertResult>('POST', `/operations/${id}:revert`),
  },

  shapes: {
    list: (
      projectId: string,
      filter: { class_id?: string; image_status?: string; tiny_only?: boolean; after?: string | null; limit?: number },
    ) =>
      request<{ items: ShapeItem[]; next?: string | null }>(
        'GET',
        `/projects/${projectId}/shapes${query({ ...filter })}`,
      ),
    cropUrl: (id: string, size = 160) => `${BASE}/annotations/${id}/crop?size=${size}`,
    bulk: (
      projectId: string,
      body: { action: 'reclass' | 'delete'; ids: string[]; target_id?: string; dry_run: boolean },
    ) => request<ClassOp>('POST', `/projects/${projectId}/annotations:bulk`, body),
  },

  health: (projectId: string) => request<Health>('GET', `/projects/${projectId}/health`),
  exportInfo: (projectId: string) =>
    request<{ order_changed: boolean; has_exported: boolean }>(
      'GET',
      `/projects/${projectId}/export-info`,
    ),

  images: {
    list: (projectId: string, filter: ImageFilter = {}) =>
      request<ImagePage>('GET', `/projects/${projectId}/images${query({ ...filter })}`),
    get: (id: string) => request<ImageItem>('GET', `/images/${id}`),
    setStatus: (id: string, status: 'todo' | 'in_progress' | 'done') =>
      request<ImageItem>('PATCH', `/images/${id}`, { status }),
    fileUrl: (id: string) => `${BASE}/images/${id}/file`,
    thumbUrl: (id: string) => `${BASE}/images/${id}/thumb`,
    importFolder: (projectId: string, folder: string) =>
      request<Job>('POST', `/projects/${projectId}/images:import-folder`, { folder }),
    upload: async (projectId: string, file: File): Promise<ImageItem> => {
      const form = new FormData();
      form.append('file', file);
      const response = await send(`/projects/${projectId}/images`, { method: 'POST', body: form });
      if (!response.ok) return fail(response);
      return (await response.json()) as ImageItem;
    },
  },

  annotations: {
    list: (imageId: string) => request<Annotation[]>('GET', `/images/${imageId}/annotations`),
    batch: (imageId: string, ops: BatchOp[]) =>
      request<{ results: OpResult[] }>('POST', `/images/${imageId}/annotations:batch`, { ops }),
  },

  jobs: {
    get: (id: string) => request<Job>('GET', `/jobs/${id}`),
    downloadUrl: (id: string) => `${BASE}/jobs/${id}/download`,
    importDataset: (projectId: string, path: string, format?: string) =>
      request<Job>('POST', `/projects/${projectId}/imports`, { path, format }),
    exportDataset: (
      projectId: string,
      format: string,
      statuses?: string[],
      copyImages = false,
      split?: { train: number; val: number; test: number; seed: number; stratify: boolean },
    ) =>
      request<Job>('POST', `/projects/${projectId}/exports`, {
        format,
        statuses,
        copy_images: copyImages,
        split,
      }),
  },
};

/** Poll a job until it finishes. Calls `onProgress` with 0 to 1. */
export async function waitForJob(id: string, onProgress?: (p: number) => void): Promise<Job> {
  for (;;) {
    const job = await api.jobs.get(id);
    onProgress?.(job.progress);
    if (job.status === 'done' || job.status === 'failed') return job;
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
}
