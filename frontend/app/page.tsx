"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Select, SelectItem } from "@heroui/select";
import { Input } from "@heroui/input";
import { Accordion, AccordionItem } from "@heroui/accordion";
import { title, subtitle } from "@/components/primitives";
import { UploadIcon, FileIcon, TrashIcon } from "@/components/icons";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const languages = [
  { key: "en", label: "English" },
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
  const router = useRouter();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [targetLanguage, setTargetLanguage] = useState<string>("");
  const [isDragOver, setIsDragOver] = useState(false);
  const [sourceLanguage, setSourceLanguage] = useState<string | null>(null);
  const [isDetectingLanguage, setIsDetectingLanguage] = useState(false);
  const [detectionError, setDetectionError] = useState<string | null>(null);
  const [documentInfo, setDocumentInfo] = useState<{ pages: number; kind: string } | null>(null);
  const [textPreview, setTextPreview] = useState<string>("");
  const [isTranslating, setIsTranslating] = useState(false);
  const [translateError, setTranslateError] = useState<string | null>(null);
  const [translatorProvider, setTranslatorProvider] = useState<string>("azure");
  const [originalPdfDataUrl, setOriginalPdfDataUrl] = useState<string | null>(null);

  // Helper function to convert File to data URL for PDF display
  const createPdfDataUrl = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => {
        if (e.target?.result) {
          resolve(e.target.result as string);
        } else {
          reject(new Error("Failed to read file"));
        }
      };
      reader.onerror = () => reject(new Error("Failed to read file"));
      reader.readAsDataURL(file);
    });
  };

  const handleFileSelect = async (file: File) => {
    if (file.type === "application/pdf") {
      setSelectedFile(file);
      setSourceLanguage(null);
      setDetectionError(null);
      setDocumentInfo(null);
      setTextPreview("");
      setTranslateError(null);
      
      // Create data URL for PDF display
      try {
        const dataUrl = await createPdfDataUrl(file);
        setOriginalPdfDataUrl(dataUrl);
      } catch (error) {
        console.error("Failed to create PDF data URL", error);
        setOriginalPdfDataUrl(null);
      }
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
    setSourceLanguage(null);
    setDetectionError(null);
    setDocumentInfo(null);
    setTextPreview("");
    setIsDetectingLanguage(false);
    setTranslateError(null);
    setIsTranslating(false);
    setOriginalPdfDataUrl(null);
  };

  const handleTranslate = async () => {
    // check if both a PDF file and a language have been selected
    if (!selectedFile || !targetLanguage){
      alert("Please select a PDF and a target language")
      return;
    }
    setIsTranslating(true);
    setTranslateError(null);
    // create form data to send pdf file and target language in post request
    const fd = new FormData();
    fd.append("file", selectedFile);
    fd.append("target_language", targetLanguage);
    fd.append("translator_provider", translatorProvider);
    // send the pdf file to the backend for extraction and translation
    try {
      const res = await fetch(`${API_BASE_URL}/translate`, {method: "POST", body: fd});
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Server Error");
      }

      // Store data and navigate to results page
      // Use IndexedDB for large PDF data to avoid sessionStorage quota limits
      const storeDataAndNavigate = () => {
        return new Promise<void>((resolve, reject) => {
          // Store text and metadata (small data) in sessionStorage
          sessionStorage.setItem("originalText", data.original_text);
          sessionStorage.setItem("translatedText", data.translated_text);
          sessionStorage.setItem("metadata", JSON.stringify({
            pages: data.pages,
            kind: data.kind,
            source_language: data.source_language,
            target_language: data.target_language,
          }));
          
          // Store both original and translated PDFs in IndexedDB
          const dbRequest = indexedDB.open("TranslationDB", 1);
          
          dbRequest.onerror = () => {
            reject(new Error("Failed to open IndexedDB"));
          };
          
          dbRequest.onsuccess = () => {
            const db = dbRequest.result;
            const transaction = db.transaction(["pdfs"], "readwrite");
            const store = transaction.objectStore("pdfs");
            
            // Store both PDFs
            const requests: Promise<void>[] = [];
            
            // Store original PDF if available
            if (originalPdfDataUrl) {
              // Extract base64 from data URL if it's a data URL
              let originalBase64: string | null = null;
              if (originalPdfDataUrl.startsWith("data:")) {
                const match = originalPdfDataUrl.match(/base64,(.+)$/);
                if (match && match[1]) {
                  originalBase64 = match[1];
                  console.log("Extracted original PDF base64, length:", originalBase64.length);
                } else {
                  console.warn("Failed to extract base64 from original PDF data URL");
                }
              }
              
              if (originalBase64) {
                const originalRequest = new Promise<void>((resolveOriginal, rejectOriginal) => {
                  const putRequest = store.put({
                    id: "originalPdf",
                    base64: originalBase64,
                  });
                  
                  putRequest.onsuccess = () => {
                    console.log("Original PDF stored successfully in IndexedDB");
                    resolveOriginal();
                  };
                  putRequest.onerror = (event) => {
                    console.error("Failed to store original PDF in IndexedDB:", event);
                    rejectOriginal(new Error("Failed to store original PDF"));
                  };
                });
                requests.push(originalRequest);
              } else {
                // If it's not a data URL or extraction failed, try to store it as-is in sessionStorage
                console.warn("Original PDF is not a data URL or extraction failed, trying sessionStorage");
                try {
                  sessionStorage.setItem("originalPdfDataUrl", originalPdfDataUrl);
                  console.log("Original PDF stored in sessionStorage as fallback");
                } catch (e) {
                  console.error("Failed to store original PDF in sessionStorage:", e);
                }
              }
            } else {
              console.warn("No original PDF data URL available to store");
            }
            
            // Store translated PDF if available
            if (data.translated_pdf_base64) {
              const translatedRequest = new Promise<void>((resolveTranslated, rejectTranslated) => {
                const putRequest = store.put({
                  id: "translatedPdf",
                  base64: data.translated_pdf_base64,
                });
                
                putRequest.onsuccess = () => resolveTranslated();
                putRequest.onerror = () => rejectTranslated(new Error("Failed to store translated PDF"));
              });
              requests.push(translatedRequest);
            }
            
            // Wait for all requests to complete
            Promise.all(requests)
              .then(() => resolve())
              .catch((error) => reject(error));
          };
          
          dbRequest.onupgradeneeded = (event) => {
            const db = (event.target as IDBOpenDBRequest).result;
            if (!db.objectStoreNames.contains("pdfs")) {
              db.createObjectStore("pdfs", { keyPath: "id" });
            }
          };
        });
      };
      
      try {
        await storeDataAndNavigate();
        // Navigate to results page after data is stored
        router.push("/results");
      } catch (error) {
        console.error("Failed to store translation data", error);
        setTranslateError("Failed to prepare translation results. The PDF may be too large.");
        setIsTranslating(false);
      }
    } catch (error) {
      console.error("Failed to translate document", error);
      const message = error instanceof Error ? error.message : "Failed to translate document";
      setTranslateError(message);
    } finally {
      setIsTranslating(false);
    }
  } 

  const formatLanguage = (code: string | null) => {
    if (!code || code === "unknown") {
      return "Unknown";
    }
    try {
      if (typeof Intl !== "undefined" && typeof Intl.DisplayNames === "function") {
        const formatter = new Intl.DisplayNames(["en"], { type: "language" });
        return formatter.of(code) ?? code.toUpperCase();
      }
    } catch {
      // ignore formatter errors
    }
    return code.toUpperCase();
  };

  useEffect(() => {
    if (!selectedFile) {
      return;
    }

    let cancelled = false;

    const detectLanguage = async () => {
      setIsDetectingLanguage(true);
      setDetectionError(null);

      const fd = new FormData();
      fd.append("file", selectedFile);

      try {
        const res = await fetch(`${API_BASE_URL}/extract`, {
          method: "POST",
          body: fd,
        });
        const data = await res.json();
        if (!res.ok) {
          const errorMessage = data?.detail || "Failed to analyze PDF";
          throw new Error(errorMessage);
        }
        if (cancelled) return;

        setSourceLanguage(data.language ?? "unknown");
        setDocumentInfo({ pages: data.pages, kind: data.kind });
        setTextPreview(data.text_preview ?? "");
      } catch (error) {
        if (cancelled) return;
        console.error("Failed to detect language", error);
        const message =
          error instanceof Error ? error.message : "Failed to detect language";
        setDetectionError(message);
        setSourceLanguage(null);
        setDocumentInfo(null);
        setTextPreview("");
      } finally {
        if (!cancelled) {
          setIsDetectingLanguage(false);
        }
      }
    };

    detectLanguage();

    return () => {
      cancelled = true;
    };
  }, [selectedFile]);

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
                  <div className="mt-4 space-y-3 text-sm text-default-600">
                    {isDetectingLanguage && <p>Detecting language...</p>}
                    {!isDetectingLanguage && detectionError && (
                      <p className="text-danger-500">
                        Could not detect language: {detectionError}
                      </p>
                    )}
                    {!isDetectingLanguage && !detectionError && (
                      <>
                        <p>
                          <span className="font-semibold">Detected language:</span>{" "}
                          {formatLanguage(sourceLanguage)}
                        </p>
                        {documentInfo && (
                          <p>
                            <span className="font-semibold">Document type:</span>{" "}
                            {documentInfo.kind === "scanned" ? "Scanned PDF" : "Digital PDF"} -{" "}
                            {documentInfo.pages} page{documentInfo.pages === 1 ? "" : "s"}
                          </p>
                        )}
                        {textPreview && (
                          <Accordion>
                            <AccordionItem
                              key="text-preview"
                              aria-label="Text Preview"
                              title="Text Preview"
                            >
                              <p className="text-xs text-default-500 whitespace-pre-wrap max-h-64 overflow-y-auto border border-default-200 rounded-md p-2 bg-white">
                                {textPreview}
                              </p>
                            </AccordionItem>
                          </Accordion>
                        )}
                      </>
                    )}
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

            {/* Translator Provider Selection */}
            <div className="space-y-4">
              <h3 className="text-lg font-semibold">Translation Provider</h3>
              <Select
                placeholder="Choose translation provider"
                selectedKeys={[translatorProvider]}
                onSelectionChange={(keys) => {
                  const selected = Array.from(keys)[0] as string;
                  setTranslatorProvider(selected);
                }}
                className="w-full"
              >
                <SelectItem key="azure">Azure Translator (Cloud)</SelectItem>
                <SelectItem key="libretranslate">LibreTranslate (Local - Free & Unlimited)</SelectItem>
              </Select>
              {translatorProvider === "libretranslate" && (
                <p className="text-sm text-default-500">
                  Make sure LibreTranslate is running at http://localhost:5000
                </p>
              )}
            </div>

            {/* Translate Button */}
            <Button
              color="primary"
              size="lg"
              className="w-full font-semibold"
              onPress={handleTranslate}
              isDisabled={!selectedFile || !targetLanguage || isTranslating}
              isLoading={isTranslating}
            >
              Translate PDF
            </Button>
            {translateError && (
              <p className="text-danger-500 text-sm">{translateError}</p>
            )}
          </div>
        </CardBody>
      </Card>

      {/* Original PDF Viewer */}
      {originalPdfDataUrl && (
        <Card className="w-full max-w-6xl">
          <CardBody className="p-6">
            <h3 className="text-lg font-semibold mb-4">Original PDF Preview</h3>
            <div className="border border-default-200 rounded-lg overflow-hidden shadow-lg">
              <embed
                src={originalPdfDataUrl}
                type="application/pdf"
                className="w-full"
                style={{ minHeight: "600px", height: "80vh" }}
                title="Original PDF"
              />
            </div>
          </CardBody>
        </Card>
      )}

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
