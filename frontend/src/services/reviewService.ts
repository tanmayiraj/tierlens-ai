import apiClient from './apiClient';
import {
  ReviewQueueResponse,
  ReviewRequest,
  ReviewResponse,
} from '../types/review';

/**
 * Fetches all pending relationships awaiting human-in-the-loop review.
 * Ordered by confidence ascending.
 */
export const getReviewQueue = async (): Promise<ReviewQueueResponse> => {
  const response = await apiClient.get<ReviewQueueResponse>('/review-queue');
  return response.data;
};

/**
 * Approves, rejects, or applies corrections and approves a pending relationship.
 */
export const reviewRelationship = async (
  relationshipId: number,
  payload: ReviewRequest
): Promise<ReviewResponse> => {
  const response = await apiClient.post<ReviewResponse>(
    `/review/${relationshipId}`,
    payload
  );
  return response.data;
};
