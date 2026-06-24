/**
 * Сервис для работы с чатом поддержки.
 */

import { apiFetch } from '$lib/utils/api';

const BASE_URL = '/api/v1/chat';

async function fetchAPI<T>(url: string, options?: RequestInit): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options?.headers,
  };

  const response = await apiFetch(url, { ...options, headers });

  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('UNAUTHORIZED');
    }

    const text = await response.text();
    let errorDetail = `HTTP ${response.status}`;
    if (text) {
      try {
        const errorJson = JSON.parse(text);
        errorDetail = errorJson.detail || errorJson.message || text;
      } catch {
        errorDetail = text;
      }
    }
    throw new Error(errorDetail);
  }

  const text = await response.text();
  if (!text) {
    return {} as unknown as T;
  }

  return JSON.parse(text) as T;
}

export interface ChatUser {
  id: string;
  email: string;
  full_name?: string | null;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender_id: string;
  sender_role: 'user' | 'admin';
  text: string;
  is_read: boolean;
  is_internal?: boolean | null;
  created_at: string;
  edited_at?: string | null;
}

export interface ChatConversation {
  id: number;
  user_id: string;
  user?: ChatUser | null;
  user_email?: string;
  user_name?: string | null;
  admin_id?: string | null;
  admin?: ChatUser | null;
  admin_email?: string | null;
  topic?: string | null;
  is_active: boolean;
  is_closed: boolean;
  status?: 'waiting_response' | 'in_progress' | 'answered' | 'closed';
  created_at: string;
  updated_at?: string | null;
  last_message_at?: string | null;
  messages: ChatMessage[];
  unread_count?: number;
  last_message_preview?: string | null;
}

export interface ChatConversationCreate {
  topic?: string | null;
}

export interface ChatMessageCreate {
  text: string;
  is_internal?: boolean;
}

export const ChatService = {
  async getConversations(includeClosed = false, limit = 20): Promise<ChatConversation[]> {
    const params = new URLSearchParams({
      include_closed: includeClosed.toString(),
      limit: limit.toString(),
    });
    return fetchAPI<ChatConversation[]>(`${BASE_URL}/conversations?${params}`);
  },

  async getConversation(conversationId: number): Promise<ChatConversation> {
    return fetchAPI<ChatConversation>(`${BASE_URL}/conversations/${conversationId}`);
  },

  async createConversation(data: ChatConversationCreate): Promise<ChatConversation> {
    return fetchAPI<ChatConversation>(`${BASE_URL}/conversations`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async sendMessage(conversationId: number, data: ChatMessageCreate): Promise<ChatMessage> {
    return fetchAPI<ChatMessage>(`${BASE_URL}/conversations/${conversationId}/messages`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  },

  async assignConversation(conversationId: number): Promise<{ status: string; message: string }> {
    return fetchAPI(`${BASE_URL}/admin/conversations/${conversationId}/assign`, {
      method: 'POST',
    });
  },

  async closeConversation(conversationId: number): Promise<{ status: string; message: string }> {
    return fetchAPI(`${BASE_URL}/admin/conversations/${conversationId}/close`, {
      method: 'POST',
    });
  },

  async updateConversationStatus(
    conversationId: number,
    status: 'waiting_response' | 'in_progress' | 'answered' | 'closed'
  ): Promise<{ status: string; message: string; conversation_status: string }> {
    return fetchAPI(`${BASE_URL}/admin/conversations/${conversationId}/status?status_value=${status}`, {
      method: 'POST',
    });
  },

  async getAdminConversations(
    status: 'all' | 'active' | 'closed' | 'unassigned' | 'waiting_response' | 'in_progress' | 'answered' = 'all',
    onlyMy = false
  ): Promise<ChatConversation[]> {
    const params = new URLSearchParams({
      status,
      only_my: String(onlyMy),
    });
    return fetchAPI<ChatConversation[]>(`${BASE_URL}/admin/conversations?${params}`);
  },
};
