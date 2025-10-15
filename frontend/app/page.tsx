"use client";

import { useState } from "react";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Select, SelectItem } from "@heroui/select";
import { Input } from "@heroui/input";
import { title, subtitle } from "@/components/primitives";
import { UploadIcon, FileIcon, TrashIcon } from "@/components/icons";

const languages = [
  { key: "es", label: "Spanish" },
  { key: "fr", label: "French" },
  { key: "de", label: "German" },
  { key: "it", label: "Italian" },
  { key: "pt", label: "Portuguese" },
  { key: "ru", label: "Russian" },
  { key: "ja", label: "Japanese" },
  { key: "ko", label: "Korean" },
  { key: "zh", label: "Chinese" },
  { key: "ar", label: "Arabic" },
  { key: "hi", label: "Hindi" },
  { key: "nl", label: "Dutch" },
  { key: "sv", label: "Swedish" },
  { key: "no", label: "Norwegian" },
  { key: "da", label: "Danish" },
];

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string>("");
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFileSelect = (file: File) => {
    if (file.type === "application/pdf") {
      setSelectedFile(file);
    } else {
      alert("Please select a PDF file");
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
  };

  const handleTranslate = async () => {
    // check if both a PDF file and a language have been selected
    if (!selectedFile || !targetLanguage){
      alert("Please select a PDF and a target language")
      return;
    }
    // create for date to send pdf file in post request
    const fd = new FormData();
    fd.append("file", selectedFile);
    // send the pdf file to the backend for text extraction
    const res = await fetch("http://127.0.0.1:8000/extract", {method: "POST", body: fd});
    const data = await res.json()
    if (!res.ok) throw new Error(data.detail || "Server Error");
    console.log(data);
  } 
    

  return (
    <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
      {/* Header */}
      <div className="inline-block max-w-2xl text-center justify-center">
        <span className={title()}>AI PDF&nbsp;</span>
        <span className={title({ color: "violet" })}>Translator</span>
        <div className={subtitle({ class: "mt-4" })}>
          Upload your PDF document and translate it to any language using advanced AI technology.
        </div>
      </div>

      {/* Main Translation Interface */}
      <Card className="w-full max-w-2xl">
        <CardBody className="p-8">
          <div className="space-y-6">
            {/* File Upload Area */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Upload PDF Document</h3>
              
              {!selectedFile ? (
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
                    Supported format: PDF (max 10MB)
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
              ) : (
                <div className="border border-default-200 rounded-lg p-4 bg-default-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <FileIcon className="text-primary" />
                      <div>
                        <p className="font-medium">{selectedFile.name}</p>
                        <p className="text-sm text-default-500">
                          {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                        </p>
                      </div>
                    </div>
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
              )}
            </div>

            {/* Language Selection */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Select Target Language</h3>
              <Select
                placeholder="Choose a language to translate to"
                selectedKeys={targetLanguage ? [targetLanguage] : []}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  setTargetLanguage(selected);
                }}
                className="w-full"
              >
                {languages.map((language) => (
                  <SelectItem key={language.key}>
                    {language.label}
                  </SelectItem>
                ))}
              </Select>
            </div>

            {/* Translate Button */}
            <Button
              color="primary"
              size="lg"
              className="w-full font-semibold"
              onPress={handleTranslate}
              isDisabled={!selectedFile || !targetLanguage}
            >
              Translate PDF
            </Button>
          </div>
        </CardBody>
      </Card>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full max-w-4xl">
        <Card>
          <CardBody className="text-center p-6">
            <div className="text-2xl mb-2">🚀</div>
            <h3 className="font-semibold mb-2">Fast Translation</h3>
            <p className="text-sm text-default-600">
              Advanced AI technology for quick and accurate translations
            </p>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody className="text-center p-6">
            <div className="text-2xl mb-2">🌍</div>
            <h3 className="font-semibold mb-2">Multiple Languages</h3>
            <p className="text-sm text-default-600">
              Support for 15+ languages with more being added regularly
            </p>
          </CardBody>
        </Card>
        
        <Card>
          <CardBody className="text-center p-6">
            <div className="text-2xl mb-2">🔒</div>
            <h3 className="font-semibold mb-2">Secure & Private</h3>
            <p className="text-sm text-default-600">
              Your documents are processed securely and never stored
            </p>
          </CardBody>
        </Card>
      </div>
    </section>
  );
}
