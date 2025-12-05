"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Select, SelectItem } from "@heroui/select";
import { Input } from "@heroui/input";
import { title } from "@/components/primitives";
import { UploadIcon, FileIcon, TrashIcon } from "@/components/icons";
import Chat from "@/components/chat";
import { getAvailableModels } from "@/lib/chat-api";

export default function ChatPage() {
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [pdfBase64, setPdfBase64] = useState<string | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [availableModels, setAvailableModels] = useState<
    Array<{ name: string; model: string }>
  >([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [useVisual, setUseVisual] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    try {
      const models = await getAvailableModels();
      setAvailableModels(models);
      if (models.length > 0 && !selectedModel) {
        setSelectedModel(models[0].name);
      }
    } catch (error) {
      console.error("Failed to load models:", error);
    }
  };

  const handleFileSelect = async (file: File) => {
    if (file.type === "application/pdf") {
      setSelectedFile(file);
      setChatError(null);

      // Convert file to base64
      const reader = new FileReader();
      reader.onload = (e) => {
        if (e.target?.result) {
          const dataUrl = e.target.result as string;
          // Extract base64 part
          const base64Match = dataUrl.match(/base64,(.+)$/);
          if (base64Match && base64Match[1]) {
            setPdfBase64(base64Match[1]);
          }
        }
      };
      reader.onerror = () => {
        setChatError("Failed to read PDF file");
      };
      reader.readAsDataURL(file);
    } else {
      setChatError("Please select a PDF file");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      handleFileSelect(file);
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    setPdfBase64(null);
    setChatError(null);
  };

  return (
    <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
      {/* Header */}
      <div className="inline-block max-w-2xl text-center justify-center">
        <span className={title()}>PDF&nbsp;</span>
        <span className={title({ color: "violet" })}>Chat Assistant</span>
      </div>

      {/* File Upload Section */}
      {!pdfBase64 && (
        <Card className="w-full max-w-2xl">
          <CardBody className="p-8">
            <div className="space-y-6">
              <h3 className="text-lg font-semibold">Upload PDF Document</h3>

              <div
                className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
                  isDragOver
                    ? "border-primary bg-primary/5"
                    : "border-default-300 hover:border-primary/50"
                }`}
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
              >
                <UploadIcon className="mx-auto mb-4 text-4xl text-default-400" />
                <p className="text-default-600 mb-2">
                  Drag and drop your PDF file here, or click to browse
                </p>
                <p className="text-sm text-default-400">
                  Supported format: PDF (max 50MB)
                </p>
                <Input
                  type="file"
                  accept=".pdf"
                  onChange={handleFileInput}
                  className="mt-4"
                  classNames={{
                    input: "cursor-pointer",
                  }}
                />
              </div>

              {chatError && (
                <div className="p-3 bg-danger-50 border border-danger-200 rounded-lg">
                  <p className="text-sm text-danger-600">{chatError}</p>
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      )}

      {/* Chat Section */}
      {pdfBase64 && (
        <div className="w-full max-w-6xl space-y-4">
          {/* File Info Card */}
          <Card>
            <CardBody className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <FileIcon className="text-primary" />
                  <div>
                    <p className="font-medium">
                      {selectedFile?.name || "PDF Document"}
                    </p>
                    <p className="text-sm text-default-500">
                      {selectedFile
                        ? `${(selectedFile.size / 1024 / 1024).toFixed(2)} MB`
                        : ""}
                    </p>
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button
                    color="primary"
                    variant="bordered"
                    onPress={() => router.push("/")}
                  >
                    Translate PDF
                  </Button>
                  <Button
                    isIconOnly
                    variant="light"
                    color="danger"
                    onPress={removeFile}
                  >
                    <TrashIcon />
                  </Button>
                </div>
              </div>
            </CardBody>
          </Card>

          {/* Chat Component */}
          <Chat
            pdfBase64={pdfBase64}
            contextType="original"
            onError={(error) => setChatError(error)}
            className="w-full"
          />
        </div>
      )}

      {/* Info Section */}
      {!pdfBase64 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
          <Card>
            <CardBody className="text-center p-6">
              <div className="text-2xl mb-2">💬</div>
              <h3 className="font-semibold mb-2">Ask Questions</h3>
              <p className="text-sm text-default-600">
                Get answers about your PDF content using AI
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardBody className="text-center p-6">
              <div className="text-2xl mb-2">📄</div>
              <h3 className="font-semibold mb-2">Extract Information</h3>
              <p className="text-sm text-default-600">
                Find specific details from your documents
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardBody className="text-center p-6">
              <div className="text-2xl mb-2">🔍</div>
              <h3 className="font-semibold mb-2">Summarize</h3>
              <p className="text-sm text-default-600">
                Get quick summaries of your PDF content
              </p>
            </CardBody>
          </Card>
        </div>
      )}
    </section>
  );
}

