"use client";

import React, { useState, useEffect } from "react";
import { DocumentList, FileUpload } from "./_components";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

const ChatWithDocumentPage = () => {
  const [activeTab, setActiveTab] = useState("documents");
  const [refreshDocuments, setRefreshDocuments] = useState(false);

  const handleUploadComplete = () => {
    setRefreshDocuments((prev) => !prev);
    setActiveTab("documents");
  };

  return (
    <div className="container max-w-6xl py-10">
      <Card>
        <CardHeader>
          <CardTitle>Chat with Document</CardTitle>
          <CardDescription>
            Upload documents and chat with them using AI
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs
            defaultValue="documents"
            value={activeTab}
            onValueChange={setActiveTab}
          >
            <TabsList className="grid w-full grid-cols-2 mb-8">
              <TabsTrigger value="documents">My Documents</TabsTrigger>
              <TabsTrigger value="upload">Upload New Document</TabsTrigger>
            </TabsList>
            <TabsContent value="documents">
              <DocumentList key={String(refreshDocuments)} />
            </TabsContent>
            <TabsContent value="upload">
              <FileUpload onUploadComplete={handleUploadComplete} />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
};

export default ChatWithDocumentPage;
