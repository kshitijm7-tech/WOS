/**
 * Thin fetch wrapper. Every request goes through here so auth headers, error handling,
 * and the API base path only need to be set in one place. Phase 2 adds the token
 * attachment logic once /api/auth exists.
 */

const BASE = ((import.meta as any).env?.VITE_API_URL as string) || "/api";



export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

// Set by AuthProvider on login/logout/startup — kept out of React state so every fetch
// call (including ones outside components) can see the latest token immediately.
let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const isJsonBody = options.body !== undefined && !isFormData;
  const headers: Record<string, string> = {
    ...(isJsonBody ? { "Content-Type": "application/json" } : {}),
    ...((options.headers as Record<string, string> | undefined) ?? {}),
  };
  if (authToken) headers.Authorization = `Bearer ${authToken}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers,
      ...options,
    });
  } catch (err: any) {
    throw new ApiError(
      `Cannot connect to API backend at ${BASE}. Please verify your backend server is running and VITE_API_URL is set in Vercel.`,
      0
    );
  }

  // Check if response is HTML (happens when static SPA server captures /api requests)
  const contentType = res.headers.get("content-type") || "";
  if (contentType.includes("text/html")) {
    throw new ApiError(
      `Backend API server is not connected (received HTML page from ${BASE}${path}). Please set the VITE_API_URL environment variable in your Vercel project settings to your deployed FastAPI backend URL.`,
      res.status
    );
  }

  if (!res.ok) {
    let message = `Request failed with status ${res.status}.`;
    try {
      const body = await res.json();
      const detail = body.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail) && detail.length > 0) {
        message = detail.map((d: { msg?: string }) => d.msg).join("; ");
      } else if (detail) {
        message = JSON.stringify(detail);
      }
    } catch {
      /* non-JSON error body, keep fallback message */
    }
    throw new ApiError(message, res.status);
  }

  // 204 No Content has no body
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}


export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
};

export async function pingDatabase() {
  return request<{ status: string; database: string }>("/ping-db");
}
