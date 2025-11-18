"use client";

import { Toaster } from "react-hot-toast";

export const ToastContainer = () => {
  return (
    <Toaster
      position="top-right"
      reverseOrder={false}
      gutter={8}
      containerStyle={{
        top: 16,
        right: 16,
      }}
      toastOptions={{
        duration: 3000,
      }}
    />
  );
};

export default ToastContainer;
