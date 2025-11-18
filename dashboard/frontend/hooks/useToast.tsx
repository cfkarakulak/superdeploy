"use client";

import toast from 'react-hot-toast';

export const useToast = () => {
  return {
    success: (message: string, duration?: number) => {
      toast.success(message, {
        duration: duration || 3000,
        style: {
          background: '#dcfce7',
          color: '#15803d',
          border: '1px solid #bbf7d0',
          borderRadius: '10px',
          padding: '12px 16px',
          fontSize: '13px',
          fontWeight: '300',
          letterSpacing: '0.03em',
        },
        iconTheme: {
          primary: '#15803d',
          secondary: '#dcfce7',
        },
      });
    },
    error: (message: string, duration?: number) => {
      toast.error(message, {
        duration: duration || 3000,
        style: {
          background: '#fef2f2',
          color: '#ef4444',
          border: '1px solid #fee2e2',
          borderRadius: '10px',
          padding: '12px 16px',
          fontSize: '13px',
          fontWeight: '300',
          letterSpacing: '0.03em',
        },
        iconTheme: {
          primary: '#ef4444',
          secondary: '#fef2f2',
        },
      });
    },
    info: (message: string, duration?: number) => {
      toast(message, {
        duration: duration || 3000,
        icon: 'ℹ️',
        style: {
          background: '#e0f2fe',
          color: '#0369a1',
          border: '1px solid #bae6fd',
          borderRadius: '10px',
          padding: '12px 16px',
          fontSize: '13px',
          fontWeight: '300',
          letterSpacing: '0.03em',
        },
      });
    },
  };
};
