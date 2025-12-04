"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardBody } from "@heroui/card";
import { Button } from "@heroui/button";
import { Modal, ModalContent, ModalHeader, ModalBody, useDisclosure } from "@heroui/modal";
import { Accordion, AccordionItem } from "@heroui/accordion";
import { title } from "@/components/primitives";

type Metadata = {
  pages: number;
  kind: string;
  source_language: string;
  target_language: string;
};

export default function ResultsPage() {
  const router = useRouter();
  const [originalPdfDataUrl, setOriginalPdfDataUrl] = useState<string | null>(null);
  const [translatedPdfDataUrl, setTranslatedPdfDataUrl] = useState<string | null>(null);
  const [originalText, setOriginalText] = useState<string>("");
  const [translatedText, setTranslatedText] = useState<string>("");
  const [metadata, setMetadata] = useState<Metadata | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fullscreenPdf, setFullscreenPdf] = useState<{ url: string; title: string } | null>(null);
  const [showOriginal, setShowOriginal] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();

  useEffect(() => {
    // Retrieve data from sessionStorage and IndexedDB
    const loadData = () => {
      const storedOriginalPdf = sessionStorage.getItem("originalPdfDataUrl");
      const storedOriginalText = sessionStorage.getItem("originalText");
      const storedTranslatedText = sessionStorage.getItem("translatedText");
      const storedMetadata = sessionStorage.getItem("metadata");

      // Load text and metadata from sessionStorage
      if (storedOriginalText) {
        setOriginalText(storedOriginalText);
      }

      if (storedTranslatedText) {
        setTranslatedText(storedTranslatedText);
      }

      if (storedMetadata) {
        try {
          setMetadata(JSON.parse(storedMetadata));
        } catch (e) {
          console.error("Failed to parse metadata", e);
        }
      }

      // Check if we have any data at all
      if (!storedOriginalPdf && !storedOriginalText && !storedTranslatedText) {
        // Try IndexedDB before showing error
        const dbRequest = indexedDB.open("TranslationDB", 1);
        dbRequest.onsuccess = () => {
          const db = dbRequest.result;
          if (!db.objectStoreNames.contains("pdfs")) {
            setError("No translation data found. Please translate a document first.");
            setIsLoading(false);
            return;
          }
        };
        dbRequest.onerror = () => {
          setError("No translation data found. Please translate a document first.");
          setIsLoading(false);
        };
      }

      // Try to get both PDFs from IndexedDB
      const dbRequest = indexedDB.open("TranslationDB", 1);
      
      dbRequest.onerror = () => {
        // Fallback to sessionStorage if IndexedDB fails
        if (storedOriginalPdf) {
          setOriginalPdfDataUrl(storedOriginalPdf);
        }
        setIsLoading(false);
      };
      
      dbRequest.onsuccess = () => {
        const db = dbRequest.result;
        
        // Check if object store exists
        if (!db.objectStoreNames.contains("pdfs")) {
          // Fallback to sessionStorage
          if (storedOriginalPdf) {
            setOriginalPdfDataUrl(storedOriginalPdf);
          }
          setIsLoading(false);
          return;
        }
        
        const transaction = db.transaction(["pdfs"], "readonly");
        const store = transaction.objectStore("pdfs");
        
        let originalLoaded = false;
        let translatedLoaded = false;
        
        const checkIfDone = () => {
          if (originalLoaded && translatedLoaded) {
            setIsLoading(false);
          }
        };
        
        // Load original PDF
        const originalRequest = store.get("originalPdf");
        originalRequest.onsuccess = () => {
          originalLoaded = true;
          if (originalRequest.result && originalRequest.result.base64) {
            try {
              // Convert base64 to blob and create blob URL (same approach as translated PDF)
              const base64Data = originalRequest.result.base64;
              const byteCharacters = atob(base64Data);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i += 1) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: "application/pdf" });
              
              // Verify blob was created correctly
              if (blob.size > 0) {
                const blobUrl = URL.createObjectURL(blob);
                setOriginalPdfDataUrl(blobUrl);
                console.log("Original PDF loaded from IndexedDB, blob size:", blob.size, "bytes");
              } else {
                console.error("Original PDF blob is empty");
                // Fallback to data URL if blob is empty
                const originalDataUrl = `data:application/pdf;base64,${base64Data}`;
                setOriginalPdfDataUrl(originalDataUrl);
              }
            } catch (error) {
              console.error("Failed to convert original PDF base64 to blob URL:", error);
              // Fallback to data URL if blob creation fails
              try {
                const originalDataUrl = `data:application/pdf;base64,${originalRequest.result.base64}`;
                setOriginalPdfDataUrl(originalDataUrl);
              } catch (e) {
                console.error("Failed to create data URL for original PDF:", e);
              }
            }
          } else if (storedOriginalPdf) {
            // Fallback to sessionStorage if not in IndexedDB
            console.log("Using original PDF from sessionStorage");
            // If it's a data URL from sessionStorage, try to convert to blob URL if it's large
            if (storedOriginalPdf.startsWith("data:")) {
              try {
                const match = storedOriginalPdf.match(/base64,(.+)$/);
                if (match && match[1]) {
                  const byteCharacters = atob(match[1]);
                  const byteNumbers = new Array(byteCharacters.length);
                  for (let i = 0; i < byteCharacters.length; i += 1) {
                    byteNumbers[i] = byteCharacters.charCodeAt(i);
                  }
                  const byteArray = new Uint8Array(byteNumbers);
                  const blob = new Blob([byteArray], { type: "application/pdf" });
                  if (blob.size > 0) {
                    const blobUrl = URL.createObjectURL(blob);
                    setOriginalPdfDataUrl(blobUrl);
                    console.log("Converted sessionStorage data URL to blob URL");
                  } else {
                    setOriginalPdfDataUrl(storedOriginalPdf);
                  }
                } else {
                  setOriginalPdfDataUrl(storedOriginalPdf);
                }
              } catch (e) {
                console.error("Failed to convert sessionStorage data URL to blob:", e);
                setOriginalPdfDataUrl(storedOriginalPdf);
              }
            } else {
              setOriginalPdfDataUrl(storedOriginalPdf);
            }
          } else {
            console.log("No original PDF found in IndexedDB or sessionStorage");
          }
          checkIfDone();
        };
        
        originalRequest.onerror = (event) => {
          originalLoaded = true;
          console.error("IndexedDB error loading original PDF:", event);
          // Fallback to sessionStorage on error
          if (storedOriginalPdf) {
            setOriginalPdfDataUrl(storedOriginalPdf);
          }
          checkIfDone();
        };
        
        // Load translated PDF
        const translatedRequest = store.get("translatedPdf");
        translatedRequest.onsuccess = () => {
          translatedLoaded = true;
          if (translatedRequest.result && translatedRequest.result.base64) {
            try {
              const byteCharacters = atob(translatedRequest.result.base64);
              const byteNumbers = new Array(byteCharacters.length);
              for (let i = 0; i < byteCharacters.length; i += 1) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
              }
              const byteArray = new Uint8Array(byteNumbers);
              const blob = new Blob([byteArray], { type: "application/pdf" });
              const blobUrl = URL.createObjectURL(blob);
              setTranslatedPdfDataUrl(blobUrl);
            } catch (error) {
              console.error("Failed to convert base64 to blob URL:", error);
              const translatedDataUrl = `data:application/pdf;base64,${translatedRequest.result.base64}`;
              setTranslatedPdfDataUrl(translatedDataUrl);
            }
          }
          checkIfDone();
        };
        
        translatedRequest.onerror = () => {
          translatedLoaded = true;
          checkIfDone();
        };
      };
      
      dbRequest.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains("pdfs")) {
          db.createObjectStore("pdfs", { keyPath: "id" });
        }
      };
    };
    
    loadData();
  }, []);

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

  const handleDownloadTranslatedPdf = () => {
    if (!translatedPdfDataUrl) {
      return;
    }

    try {
      // If it's already a blob URL, use it directly
      if (translatedPdfDataUrl.startsWith("blob:")) {
        const link = document.createElement("a");
        link.href = translatedPdfDataUrl;
        link.download = `translated_document_${metadata?.target_language || "translated"}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        // Extract base64 from data URL
        const base64Match = translatedPdfDataUrl.match(/base64,(.+)$/);
        if (!base64Match) {
          setError("Failed to extract PDF data for download.");
          return;
        }
        
        const base64 = base64Match[1];
        const byteCharacters = atob(base64);
        const byteNumbers = new Array(byteCharacters.length);
        for (let i = 0; i < byteCharacters.length; i += 1) {
          byteNumbers[i] = byteCharacters.charCodeAt(i);
        }
        const byteArray = new Uint8Array(byteNumbers);
        const blob = new Blob([byteArray], { type: "application/pdf" });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        const baseName = "translated_document";
        link.href = url;
        link.download = `${baseName}_${metadata?.target_language || "translated"}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
      }
    } catch (error) {
      console.error("Failed to prepare translated PDF", error);
      setError("Failed to prepare translated PDF for download.");
    }
  };

  const handleFullscreen = (url: string, title: string) => {
    setFullscreenPdf({ url, title });
    onOpen();
  };

  const handleTranslateAnother = () => {
    // Revoke blob URLs if they exist
    if (translatedPdfDataUrl && translatedPdfDataUrl.startsWith("blob:")) {
      URL.revokeObjectURL(translatedPdfDataUrl);
    }
    if (originalPdfDataUrl && originalPdfDataUrl.startsWith("blob:")) {
      URL.revokeObjectURL(originalPdfDataUrl);
    }
    
    // Clean up session storage and IndexedDB
    sessionStorage.removeItem("originalPdfDataUrl");
    sessionStorage.removeItem("originalText");
    sessionStorage.removeItem("translatedText");
    sessionStorage.removeItem("metadata");
    
    // Clean up IndexedDB
    const dbRequest = indexedDB.open("TranslationDB", 1);
    dbRequest.onsuccess = () => {
      const db = dbRequest.result;
      if (db.objectStoreNames.contains("pdfs")) {
        const transaction = db.transaction(["pdfs"], "readwrite");
        const store = transaction.objectStore("pdfs");
        store.delete("originalPdf");
        store.delete("translatedPdf");
      }
    };
    
    router.push("/");
  };
  
  // Cleanup blob URLs on unmount
  useEffect(() => {
    return () => {
      if (translatedPdfDataUrl && translatedPdfDataUrl.startsWith("blob:")) {
        URL.revokeObjectURL(translatedPdfDataUrl);
      }
      if (originalPdfDataUrl && originalPdfDataUrl.startsWith("blob:")) {
        URL.revokeObjectURL(originalPdfDataUrl);
      }
    };
  }, [translatedPdfDataUrl, originalPdfDataUrl]);

  if (isLoading) {
    return (
      <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
        <div className="text-center">
          <p className="text-lg">Loading translation results...</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="flex flex-col items-center justify-center gap-8 py-8 md:py-10">
        <Card className="w-full max-w-2xl">
          <CardBody className="p-8 text-center">
            <p className="text-danger-500 mb-4">{error}</p>
            <Button color="primary" onPress={handleTranslateAnother}>
              Translate Another Document
            </Button>
          </CardBody>
        </Card>
      </section>
    );
  }

  return (
    <section className="flex flex-col items-center gap-8 py-8 md:py-10 w-full">
      {/* Header */}
      <div className="inline-block max-w-2xl text-center justify-center">
        <span className={title()}>Translation&nbsp;</span>
        <span className={title({ color: "violet" })}>Results</span>
      </div>

      {/* Metadata Card */}
      {metadata && (
        <Card className="w-full max-w-[98vw]">
          <CardBody className="p-6">
            <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div className="space-y-2">
                <p className="font-semibold text-lg">
                  {formatLanguage(metadata.source_language)} → {formatLanguage(metadata.target_language)}
                </p>
                <p className="text-sm text-default-500">
                  {metadata.pages} page{metadata.pages === 1 ? "" : "s"} ·{" "}
                  {metadata.kind === "scanned" ? "Scanned PDF" : "Digital PDF"}
                </p>
              </div>
              <div className="flex gap-2">
                {translatedPdfDataUrl && (
                  <Button color="secondary" onPress={handleDownloadTranslatedPdf}>
                    Download Translated PDF
                  </Button>
                )}
                <Button color="primary" variant="bordered" onPress={handleTranslateAnother}>
                  Translate Another
                </Button>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* PDF Viewer with Toggle */}
      <div className="w-full max-w-[98vw]">
        <Card className="w-full">
          <CardBody className="p-1">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <h3 className="text-lg font-semibold">
                  {showOriginal ? "Original PDF" : "Translated PDF"}
                </h3>
                {originalPdfDataUrl && translatedPdfDataUrl && (
                  <Button
                    size="sm"
                    variant="bordered"
                    onPress={() => setShowOriginal(!showOriginal)}
                  >
                    {showOriginal ? "Show Translated" : "Show Original"}
                  </Button>
                )}
              </div>
              <Button
                size="sm"
                variant="light"
                onPress={() => handleFullscreen(
                  showOriginal && originalPdfDataUrl ? originalPdfDataUrl : translatedPdfDataUrl || "",
                  showOriginal ? "Original PDF" : "Translated PDF"
                )}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={1.5}
                  stroke="currentColor"
                  className="w-5 h-5"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15"
                  />
                </svg>
              </Button>
            </div>
            <div className="border border-default-200 rounded-lg overflow-hidden shadow-lg relative">
              {showOriginal ? (
                originalPdfDataUrl ? (
                  <iframe
                    key={`original-${Date.now()}`}
                    src={originalPdfDataUrl}
                    className="w-full"
                    style={{ minHeight: "850px", height: "95vh" }}
                    title="Original PDF"
                    onLoad={() => console.log("Original PDF iframe loaded successfully")}
                    onError={(e) => {
                      console.error("Original PDF iframe error:", e);
                      setError("Failed to load original PDF. The file may be corrupted or too large.");
                    }}
                  />
                ) : (
                  <div className="border border-default-200 rounded-lg p-8 text-center flex items-center justify-center" style={{ minHeight: "850px", height: "95vh" }}>
                    <p className="text-default-500">Original PDF is not available</p>
                  </div>
                )
              ) : translatedPdfDataUrl ? (
                <iframe
                  key={`translated-${Date.now()}`}
                  src={translatedPdfDataUrl}
                  className="w-full"
                  style={{ minHeight: "850px", height: "95vh" }}
                  title="Translated PDF"
                />
              ) : (
                <div className="border border-default-200 rounded-lg p-8 text-center flex items-center justify-center" style={{ minHeight: "850px", height: "95vh" }}>
                  <p className="text-default-500">Translated PDF is being loaded...</p>
                </div>
              )}
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Fullscreen PDF Modal */}
      <Modal
        isOpen={isOpen}
        onClose={onClose}
        size="full"
        scrollBehavior="inside"
        classNames={{
          base: "max-w-full",
          wrapper: "p-0",
        }}
      >
        <ModalContent>
          <ModalHeader className="flex items-center justify-between">
            <span>{fullscreenPdf?.title}</span>
            <Button
              isIconOnly
              variant="light"
              size="sm"
              onPress={onClose}
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
                className="w-6 h-6"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </Button>
          </ModalHeader>
          <ModalBody className="p-0">
            {fullscreenPdf && (
              <iframe
                src={fullscreenPdf.url}
                className="w-full"
                style={{ minHeight: "calc(100vh - 120px)", height: "calc(100vh - 120px)" }}
                title={fullscreenPdf.title}
              />
            )}
          </ModalBody>
        </ModalContent>
      </Modal>

      {/* Text Preview Accordion */}
      {(originalText || translatedText) && (
        <Card className="w-full max-w-[98vw]">
          <CardBody className="p-6">
            <Accordion>
              {originalText ? (
                <AccordionItem
                  key="original-text"
                  aria-label="Original Text"
                  title="Original Text Preview"
                >
                  <p className="text-sm text-default-500 whitespace-pre-wrap max-h-96 overflow-y-auto border border-default-200 rounded-md p-4 bg-default-50">
                    {originalText.slice(0, 5000)}
                    {originalText.length > 5000 ? "..." : ""}
                  </p>
                </AccordionItem>
              ) : null}
              {translatedText ? (
                <AccordionItem
                  key="translated-text"
                  aria-label="Translated Text"
                  title="Translated Text Preview"
                >
                  <p className="text-sm text-default-500 whitespace-pre-wrap max-h-96 overflow-y-auto border border-default-200 rounded-md p-4 bg-default-50">
                    {translatedText.slice(0, 5000)}
                    {translatedText.length > 5000 ? "..." : ""}
                  </p>
                </AccordionItem>
              ) : null}
            </Accordion>
          </CardBody>
        </Card>
      )}
    </section>
  );
}

