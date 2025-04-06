"use server";

import prisma from "@/lib/prisma";
import bcrypt from "bcrypt";
import { verifyTurnstileToken } from "@/lib/turnstile";

export async function loginEmployee(payload: {
  email: string;
  password: string;
  turnstileToken: string;
}) {
  const { email, password, turnstileToken } = payload;

  // Validate turnstile token
  const isValid = await verifyTurnstileToken(turnstileToken);
  if (!isValid) {
    return { error: "Invalid CAPTCHA verification" };
  }

  if (!email || !password) {
    return { error: "Missing required fields" };
  }

  try {
    const employee = await prisma.employee.findUnique({
      where: {
        email,
      },
    });

    if (!employee) {
      return { error: "Invalid credentials" };
    }

    const match = await bcrypt.compare(password, employee.password);

    if (!match) {
      return { error: "Invalid credentials" };
    }

    // Remove password from response
    const employeeWithoutPassword = { ...employee, password: undefined };

    return { employee: employeeWithoutPassword };
  } catch (error) {
    console.error(error);
    return { error: "Something went wrong" };
  }
}


export async function loginHR(payload: {
    email: string;
    password: string;
    turnstileToken: string;
  }) {
    const { email, password, turnstileToken } = payload;
  
    // Validate turnstile token
    const isValid = await verifyTurnstileToken(turnstileToken);
    if (!isValid) {
      return { error: "Invalid CAPTCHA verification" };
    }
  
    if (!email || !password) {
      return { error: "Missing required fields" };
    }
  
    try {
      const recruiter = await prisma.recruiter.findUnique({
        where: {
          email,
        },
      });
  
      if (!recruiter) {
        return { error: "Invalid credentials" };
      }
  
      const match = await bcrypt.compare(password, recruiter.password);
  
      if (!match) {
        return { error: "Invalid credentials" };
      }
  
      // Remove password from response
      const recruiterWithoutPassword = { ...recruiter, password: undefined };
  
      return { recruiter: recruiterWithoutPassword };
    } catch (error) {
      console.error(error);
      return { error: "Something went wrong" };
    }
  }

  export async function createApplicant(payload: {
    name: string;
    email: string;
    phone: string;
    password: string;
    turnstileToken?: string;
  }) {
    const { name, email, phone, password, turnstileToken } = payload;
  
    // Validate turnstile token if provided
    if (turnstileToken) {
      const isValid = await verifyTurnstileToken(turnstileToken);
      if (!isValid) {
        return { error: "Invalid CAPTCHA verification" };
      }
    }
  
    if (!name || !email || !phone || !password) {
      return { error: "Missing required fields" };
    }
  
    try {
      const existingApplicant = await prisma.applicant.findUnique({
        where: {
          email,
        },
      });
  
      if (existingApplicant) {
        return { error: "Email already in use" };
      }
  
      const hashedPassword = await bcrypt.hash(password, 10);
  
      const applicant = await prisma.applicant.create({
        data: {
          name,
          email,
          phone,
          password: hashedPassword,
        },
      });
  
      // Remove password from response
      const applicantWithoutPassword = { ...applicant, password: undefined };
  
      return { applicant: applicantWithoutPassword };
    } catch (error) {
      console.error(error);
      return { error: "Something went wrong" };
    }
  }


  export async function loginApplicant(payload: {
    email: string;
    password: string;
    turnstileToken: string;
  }) {
    const { email, password, turnstileToken } = payload;
  
    // Validate turnstile token
    const isValid = await verifyTurnstileToken(turnstileToken);
    if (!isValid) {
      return { error: "Invalid CAPTCHA verification" };
    }
  
    if (!email || !password) {
      return { error: "Missing required fields" };
    }
  
    try {
      const applicant = await prisma.applicant.findUnique({
        where: {
          email,
        },
      });
  
      if (!applicant) {
        return { error: "Invalid credentials" };
      }
  
      const match = await bcrypt.compare(password, applicant.password);
  
      if (!match) {
        return { error: "Invalid credentials" };
      }
  
      // Remove password from response
      const applicantWithoutPassword = { ...applicant, password: undefined };
  
      return { applicant: applicantWithoutPassword };
    } catch (error) {
      console.error(error);
      return { error: "Something went wrong" };
    }
  }
  