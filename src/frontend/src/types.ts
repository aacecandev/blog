export interface PostSummary {
  slug: string;
  title: string;
  date: string;
  description?: string | null;
  tags: string[];
}

export interface PostDetail {
  meta: PostSummary;
  content: string;
}

export interface PostListResponse {
  posts: PostSummary[];
  total: number;
  limit: number;
  offset: number;
}
