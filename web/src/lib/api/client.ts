import type {
  Activity,
  AppSettings,
  Annotation,
  ApiToken,
  AttrDef,
  AuthStatus,
  BatchOp,
  ClassOp,
  Comment,
  ConnectedFolder,
  ConnectResult,
  FolderListing,
  FormatInfo,
  Health,
  ImageItem,
  ImagePage,
  Inbox,
  Invite,
  InviteInfo,
  Job,
  Lock,
  Member,
  MlStatus,
  OperationInfo,
  OpResult,
  Person,
  Project,
  ProjectClass,
  RevertResult,
  Role,
  ShapeItem,
  ShuffleResult,
  SplitState,
  ShareInfo,
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
  if (response.status === 401 && data?.code === 'unauthorized') onUnauthorized?.();
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
  split?: string;
  after?: string | null;
  limit?: number;
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;

/** Called when the server says the session is gone, so the app can show the sign-in screen. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler;
}

export const api = {
  auth: {
    status: () => request<AuthStatus>('GET', '/auth/status'),
    setup: (email: string, name: string, password: string, setupCode = '') =>
      request<Person>('POST', '/auth/setup', { email, name, password, setup_code: setupCode }),
    login: (email: string, password: string) =>
      request<Person>('POST', '/auth/login', { email, password }),
    logout: () => request<void>('POST', '/auth/logout'),
    invite: (token: string) =>
      request<InviteInfo>('GET', `/auth/invites/${token}`),
    accept: (token: string, email: string, name: string, password: string) =>
      request<Person>('POST', '/auth/accept', { token, email, name, password }),
    createInvite: (projectId: string | null, role: Exclude<Role, 'owner'>) =>
      request<Invite>('POST', '/invites', {
        project_id: projectId,
        role,
      }),
    tokens: () => request<ApiToken[]>('GET', '/auth/tokens'),
    createToken: (name: string) => request<ApiToken>('POST', '/auth/tokens', { name }),
    revokeToken: (id: string) => request<void>('DELETE', `/auth/tokens/${id}`),
  },

  users: {
    list: () => request<Person[]>('GET', '/users'),
    create: (email: string, name: string, password: string, isAdmin: boolean) =>
      request<Person>('POST', '/users', { email, name, password, is_admin: isAdmin }),
    setPassword: (userId: string, password: string) =>
      request<Person>('POST', `/users/${userId}:password`, { password }),
    setAdmin: (userId: string, isAdmin: boolean) =>
      request<Person>('POST', `/users/${userId}:admin`, { is_admin: isAdmin }),
    setDisabled: (userId: string, disabled: boolean) =>
      request<Person>('POST', `/users/${userId}:${disabled ? 'disable' : 'enable'}`),
  },

  members: {
    list: (projectId: string) => request<Member[]>('GET', `/projects/${projectId}/members`),
    set: (projectId: string, userId: string, role: Role) =>
      request<Member[]>('PUT', `/projects/${projectId}/members/${userId}`, { role }),
    remove: (projectId: string, userId: string) =>
      request<Member[]>('DELETE', `/projects/${projectId}/members/${userId}`),
  },

  work: {
    next: (projectId: string) =>
      request<{ image: ImageItem | null }>('POST', `/projects/${projectId}/next`),
    assign: (projectId: string, imageIds: string[], assigneeId: string | null) =>
      request<{ assigned: number }>('POST', `/projects/${projectId}/images:assign`, {
        image_ids: imageIds,
        assignee_id: assigneeId,
      }),
    lock: (imageId: string) => request<Lock>('POST', `/images/${imageId}/lock`),
    unlock: (imageId: string) => request<void>('DELETE', `/images/${imageId}/lock`),
    takeOver: (imageId: string) => request<Lock>('POST', `/images/${imageId}/lock:take-over`),
    setStatus: (imageId: string, status: string) =>
      request<ImageItem>('PATCH', `/images/${imageId}`, { status }),
    comments: (imageId: string) => request<Comment[]>('GET', `/images/${imageId}/comments`),
    comment: (imageId: string, body: string, x?: number, y?: number) =>
      request<Comment>('POST', `/images/${imageId}/comments`, { body, x, y }),
    resolve: (commentId: string, resolved: boolean) =>
      request<Comment>('POST', `/comments/${commentId}:resolve`, { resolved }),
    activity: (projectId: string) =>
      request<Activity[]>('GET', `/projects/${projectId}/activity`),
    setReview: (projectId: string, enabled: boolean) =>
      request<Project>('PATCH', `/projects/${projectId}`, { review_enabled: enabled }),
    inbox: () => request<Inbox>('GET', '/inbox'),
  },

  formats: () => request<FormatInfo[]>('GET', '/formats'),

  projects: {
    list: (q?: string) => request<Project[]>('GET', `/projects${query({ q })}`),
    get: (id: string) => request<Project>('GET', `/projects/${id}`),
    create: (name: string, annotationTypes?: string[]) =>
      request<Project>('POST', '/projects', { name, annotation_types: annotationTypes }),
    rename: (id: string, name: string) => request<Project>('PATCH', `/projects/${id}`, { name }),
    remove: (id: string) => request<void>('DELETE', `/projects/${id}`),
    createSample: () => request<Project>('POST', '/samples'),
  },

  classes: {
    list: (projectId: string) => request<ProjectClass[]>('GET', `/projects/${projectId}/classes`),
    create: (projectId: string, name: string, color?: string) =>
      request<ProjectClass>('POST', `/projects/${projectId}/classes`, { name, color }),
    update: (
      id: string,
      patch: {
        name?: string;
        color?: string;
        attr_schema?: AttrDef[];
        skeleton?: { names: string[]; edges: [number, number][] };
      },
    ) =>
      request<ProjectClass>('PATCH', `/classes/${id}`, patch),
    reorder: (projectId: string, ids: string[]) =>
      request<void>('POST', `/projects/${projectId}/classes:reorder`, { class_ids: ids }),
    merge: (id: string, targetId: string, dryRun: boolean) =>
      request<ClassOp>('POST', `/classes/${id}:merge`, { target_id: targetId, dry_run: dryRun }),
    remove: (id: string, dryRun: boolean) =>
      request<ClassOp>('POST', `/classes/${id}:delete`, { dry_run: dryRun }),
  },

  splits: {
    get: (projectId: string) => request<SplitState>('GET', `/projects/${projectId}/splits`),
    shuffle: (
      projectId: string,
      body: {
        ratios: Record<string, number>;
        seed: number;
        stratify: boolean;
        only_unassigned: boolean;
        dry_run: boolean;
      },
    ) => request<ShuffleResult>('POST', `/projects/${projectId}/splits:shuffle`, body),
    assign: (projectId: string, imageIds: string[], split: string | null) =>
      request<{ changed: number }>('POST', `/projects/${projectId}/images:assign-split`, {
        image_ids: imageIds,
        split,
      }),
  },

  settings: {
    get: () => request<AppSettings>('GET', '/settings'),
    save: (values: Record<string, unknown>) =>
      request<AppSettings>('PUT', '/settings', { values }),
    testDatabase: (url: string) =>
      request<{ ok: boolean; message: string }>('POST', '/settings/test-database', { url }),
    restart: () => request<{ restarting: boolean }>('POST', '/settings/restart'),
    backup: () => request<Job>('POST', '/settings/backup'),
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

  ml: {
    status: () => request<MlStatus>('GET', '/ml'),
    addModel: async (file: File): Promise<{ name: string; classes: string[] | null }> => {
      const form = new FormData();
      form.append('file', file);
      const response = await send('/ml/models', { method: 'POST', body: form });
      if (!response.ok) return fail(response);
      return (await response.json()) as { name: string; classes: string[] | null };
    },
    prelabel: (
      projectId: string,
      body: {
        model: string;
        threshold: number;
        only_unlabeled: boolean;
        create_missing_classes: boolean;
        class_names?: string[];
      },
    ) => request<Job>('POST', `/projects/${projectId}/prelabel`, body),
  },

  share: {
    get: () => request<ShareInfo>('GET', '/share'),
    qrUrl: (text: string) => `${BASE}/share/qr.svg${query({ text })}`,
  },

  folders: {
    browse: (path?: string) => request<FolderListing>('GET', `/folders${query({ path })}`),
    connected: (projectId: string) =>
      request<ConnectedFolder[]>('GET', `/projects/${projectId}/folders`),
    connect: (projectId: string, path: string) =>
      request<ConnectResult>('POST', `/projects/${projectId}/folders`, { path }),
    rescan: (projectId: string, folderId: string) =>
      request<Job>('POST', `/projects/${projectId}/folders/${folderId}:rescan`),
    disconnect: (projectId: string, folderId: string) =>
      request<void>('DELETE', `/projects/${projectId}/folders/${folderId}`),
  },

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
      useSavedSplits = true,
    ) =>
      request<Job>('POST', `/projects/${projectId}/exports`, {
        format,
        statuses,
        copy_images: copyImages,
        split,
        use_saved_splits: useSavedSplits,
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
