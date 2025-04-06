"use client";

import { loginEmployee } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { setCookie } from "cookies-next";
import { toast } from "sonner";

const Page = () => {
  const router = useRouter();

  interface Payload {
    email: string;
    password: string;
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl">
        <div className="flex flex-col gap-6">
          <Card className="overflow-hidden">
            <CardContent className="grid p-0 md:grid-cols-2">
              <form
                className="p-6 md:p-8"
                action={async (e) => {
                  const formData = Object.fromEntries(e.entries());

                  const payload: Payload = {
                    email: formData.email as string,
                    password: formData.password as string,
                  };

                  const employee = await loginEmployee(payload);

                  if (!employee) {
                    toast.error("Invalid credentials");
                    return;
                  } else {
                    setCookie("effentoken", employee, {
                      maxAge: 60 * 60 * 24 * 7,
                    });

                    toast.success("Account created successfully");

                    router.push("/employee/dashboard");
                  }
                }}
              >
                <div className="flex flex-col gap-6">
                  <div className="flex flex-col items-center text-center">
                    <h1 className="text-2xl font-bold">Welcome to Effen AI</h1>
                    <p className="text-balance text-muted-foreground">
                      Login to your Employee Account
                    </p>
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      name="email"
                      type="email"
                      placeholder="Enter your email"
                      required
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="password">Password</Label>
                    <Input
                      id="password"
                      name="password"
                      type="password"
                      placeholder="Enter your password"
                      required
                    />
                  </div>
                  <Button type="submit" className="w-full">
                    Login
                  </Button>
                  <div className="text-center text-sm">
                    Don{`'`}t have an account?{" "}
                    <Link
                      href="./register"
                      className="underline underline-offset-4"
                    >
                      Signup
                    </Link>
                  </div>
                </div>
              </form>
              <div className="relative hidden bg-white md:block">
                <Image
                  src="/logo-square.png"
                  alt="Image"
                  className="absolute inset-0 w-full my-auto object-contain dark:brightness-[0.2] dark:grayscale"
                  width={800}
                  height={800}
                />
              </div>
            </CardContent>
          </Card>
          <div className="text-balance text-center text-xs text-muted-foreground [&_a]:underline [&_a]:underline-offset-4 hover:[&_a]:text-primary">
            By clicking continue, you agree to our{" "}
            <Link href="/">Terms of Service</Link> and{" "}
            <Link href="/">Privacy Policy</Link>.
          </div>
        </div>
      </div>
    </div>
  );
};

export default Page;
