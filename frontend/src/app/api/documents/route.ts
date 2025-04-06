import { NextRequest, NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
// import { getServerSession } from "next-auth/next";
// import { authOptions } from "@/lib/auth";

// Hardcoded employee ID
const EMPLOYEE_ID = "7c7ca739-ffd0-41af-b3a3-312143523a0a";

export async function POST(req: NextRequest) {
  try {
    // Using hardcoded employee ID instead of getting it from session
    const employeeId = EMPLOYEE_ID;
    
    // Get request body
    const { title, fileType, fileSize, filePath, content } = await req.json();
    
    // Validate required fields
    if (!title || !fileType || !fileSize || !filePath) {
      return NextResponse.json(
        { error: "Missing required fields" },
        { status: 400 }
      );
    }
    
    // Create document in database
    const document = await prisma.document.create({
      data: {
        title,
        fileType,
        fileSize,
        filePath,
        content: content || "",
        employeeId,
      },
    });
    
    return NextResponse.json(document, { status: 201 });
    
  } catch (error) {
    console.error("Error creating document:", error);
    return NextResponse.json(
      { error: "Failed to create document" },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  try {
    // Using hardcoded employee ID instead of getting it from session
    const employeeId = EMPLOYEE_ID;
    
    // Get documents for this employee
    const documents = await prisma.document.findMany({
      where: {
        employeeId,
        isArchived: false,
      },
      orderBy: {
        createdAt: 'desc',
      },
    });
    
    return NextResponse.json(documents);
    
  } catch (error) {
    console.error("Error fetching documents:", error);
    return NextResponse.json(
      { error: "Failed to fetch documents" },
      { status: 500 }
    );
  }
}