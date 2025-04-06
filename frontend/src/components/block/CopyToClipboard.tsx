"use client";

import { ReactNode } from "react";
import { toast } from "sonner";

interface CopyToClipboardProps {
  children: ReactNode | string;
  text: string;
}

const CopyToClipboard = ({ children, text }: CopyToClipboardProps) => {
  const handleCopy = () => {
    navigator.clipboard
      .writeText(text)
      .then(() => {
        toast.success("Copied to clipboard!");
      })
      .catch((err) => {
        toast.error("Failed to copy");
        console.error("Failed to copy text: ", err);
      });
  };

  return <span onClick={handleCopy}>{children}</span>;
};

export default CopyToClipboard;
