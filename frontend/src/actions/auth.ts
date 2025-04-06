"use server";

import prisma from "@/lib/prisma";
import bcrypt from "bcrypt";
import { verifyTurnstileToken } from "@/lib/turnstile";

export async function createEmployee(payload: {
  firstName: string;
  lastName: string;
  email: string;
  password: string;
}) {
  const { firstName, lastName, email, password } = payload;

  const hashedPassword = await bcrypt.hash(password, 10);

  const employee = await prisma.employee.create({
    data: {
      firstName,
      lastName,
      email,
      password: hashedPassword,
      companyId: "27f32072-d75b-4d4f-ab5e-83ae10a7693a",
    },
  });

  return employee;
}

export async function loginEmployee(payload: {
  email: string;
  password: string;
}) {
  const { email, password } = payload;

  const employee = await prisma.employee.findUnique({
    where: {
      email,
    },
  });

  if (!employee) {
    return null;
  }

  const isPasswordValid = await bcrypt.compare(password, employee.password);

  if (!isPasswordValid) {
    return null;
  }

  const { password: _, ...employeeWithoutPassword } = employee;
  return employeeWithoutPassword;
}
