"use client";

import React, { useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { uploadFile } from "@/lib/uploadFile";
import { Loader2, UploadCloud } from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";

interface FileUploadProps {
  onUploadComplete?: () => void;
}

export function FileUpload({ onUploadComplete }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [documentTitle, setDocumentTitle] = useState("");
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      setFile(selectedFile);

      // Auto-populate title with filename (without extension)
      const fileName = selectedFile.name.split(".").slice(0, -1).join(".");
      if (!documentTitle) {
        setDocumentTitle(fileName);
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();

    if (!file || !documentTitle) {
      toast({
        title: "Missing information",
        description: "Please select a file and provide a title",
        variant: "destructive",
      });
      return;
    }

    try {
      setUploading(true);

      // Simulate progress for better UX
      const progressInterval = setInterval(() => {
        setUploadProgress((prev) => {
          const newProgress = Math.min(prev + 5, 90);
          return newProgress;
        });
      }, 200);

      // Get file extension
      const fileExt = file.name.split(".").pop() || "";

      // Upload file
      const filePath = await uploadFile({
        file,
        fileExt,
        folderPath: "documents", // Store in documents folder
      });

      // Save document to database
      const response = await fetch("/api/documents", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: documentTitle,
          fileType: fileExt,
          fileSize: file.size,
          filePath,
          content: "", // Initially empty, might be filled by processing service
        }),
      });

      clearInterval(progressInterval);

      if (!response.ok) {
        throw new Error("Failed to save document");
      }

      setUploadProgress(100);

      toast({
        title: "Document uploaded",
        description: "Your document has been successfully uploaded",
      });

      // Reset form
      setTimeout(() => {
        setFile(null);
        setDocumentTitle("");
        setUploading(false);
        setUploadProgress(0);

        // Notify parent that upload is complete
        if (onUploadComplete) {
          onUploadComplete();
        }
      }, 1000);
    } catch (error) {
      console.error("Error uploading document:", error);
      toast({
        title: "Upload failed",
        description:
          error instanceof Error ? error.message : "An unknown error occurred",
        variant: "destructive",
      });
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upload New Document</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <Label htmlFor="title">Document Title</Label>
            <Input
              id="title"
              value={documentTitle}
              onChange={(e) => setDocumentTitle(e.target.value)}
              placeholder="Enter document title"
              disabled={uploading}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="file">Upload File</Label>
            <div className="border-2 border-dashed border-gray-300 rounded-md p-6 flex flex-col items-center justify-center">
              {!file ? (
                <>
                  <UploadCloud className="h-10 w-10 text-gray-400 mb-2" />
                  <div className="text-sm text-gray-600 mb-4">
                    <label
                      htmlFor="file"
                      className="cursor-pointer text-blue-600 hover:underline"
                    >
                      Click to upload
                    </label>{" "}
                    or drag and drop
                  </div>
                  <Input
                    id="file"
                    type="file"
                    onChange={handleFileChange}
                    accept=".pdf,.doc,.docx,.txt"
                    className="hidden"
                    disabled={uploading}
                  />
                </>
              ) : (
                <div className="text-sm text-gray-600 mb-4">
                  <div className="font-medium">{file.name}</div>
                  <div className="text-xs text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </div>
                  {!uploading && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setFile(null)}
                    >
                      Change
                    </Button>
                  )}
                </div>
              )}
            </div>
          </div>

          {uploadProgress > 0 && (
            <div className="space-y-2">
              <Label>Upload Progress</Label>
              <Progress value={uploadProgress} className="h-2" />
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={!file || !documentTitle || uploading}
          >
            {uploading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Uploading...
              </>
            ) : (
              "Upload Document"
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}