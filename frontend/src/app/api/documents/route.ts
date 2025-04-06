import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { getServerSession } from "next-auth";
// import { authOptions } from "@/lib/auth";

export async function GET() {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session || !session.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    
    // Get employee ID from session
    const employee = await prisma.employee.findUnique({
      where: {
        email: session.user.email,
      },
      select: {
        id: true,
      },
    });

    if (!employee) {
      return NextResponse.json({ error: "Employee not found" }, { status: 404 });
    }

    // Get documents for this employee
    const documents = await prisma.document.findMany({
      where: {
        employeeId: employee.id,
        isArchived: false,
      },
      orderBy: {
        createdAt: "desc",
      },
    });

    return NextResponse.json(documents);
  } catch (error) {
    console.error("Error fetching documents:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const session = await getServerSession(authOptions);
    
    if (!session || !session.user) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }
    
    const { title, fileType, fileSize, filePath, content = "" } = await req.json();
    
    if (!title || !fileType || !fileSize) {
      return NextResponse.json({ error: "Missing required fields" }, { status: 400 });
    }
    
    // Get employee ID from session
    const employee = await prisma.employee.findUnique({
      where: {
        email: session.user.email,
      },
      select: {
        id: true,
      },
    });

    if (!employee) {
      return NextResponse.json({ error: "Employee not found" }, { status: 404 });
    }
    
    // Create document in database
    const document = await prisma.document.create({
      data: {
        title,
        fileType,
        fileSize,
        filePath,
        content: content || "",
        employeeId: employee.id
      },
    });

    return NextResponse.json(document, { status: 201 });
  } catch (error) {
    console.error("Error creating document:", error);
    return NextResponse.json({ error: "Failed to create document" }, { status: 500 });
  }
}

export async function DELETE(
    req: Request,
    { params }: { params: { id: string } }
  ) {
    try {
      const session = await getServerSession(authOptions);
  
      if (!session || !session.user) {
        return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
      }
  
      const id = params.id;
  
      // Get document to check ownership
      const document = await prisma.document.findUnique({
        where: { id },
        include: {
          employee: {
            select: {
              email: true,
            },
          },
        },
      });
  
      if (!document) {
        return NextResponse.json({ error: "Document not found" }, { status: 404 });
      }
  
      // Check if the user owns this document
      if (document.employee.email !== session.user.email) {
        return NextResponse.json({ error: "Forbidden" }, { status: 403 });
      }
  
      // Delete the document
      await prisma.document.delete({
        where: { id },
      });
  
      return NextResponse.json({ success: true });
    } catch (error) {
      console.error("Error deleting document:", error);
      return NextResponse.json(
        { error: "Failed to delete document" },
        { status: 500 }
      );
    }
  }