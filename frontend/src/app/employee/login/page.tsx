"use client";

import { loginEmployee } from "@/actions/auth";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Turnstile } from "@/components/ui/turnstile";
import { useForm } from "react-hook-form";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { setCookie } from "cookies-next";
import { toast } from "sonner";
import { useState } from "react";
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";

// Define form schema with Zod
const formSchema = z.object({
  email: z.string().email("Please enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

const Page = () => {
  const router = useRouter();
  const [turnstileToken, setTurnstileToken] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);

  // Initialize form with react-hook-form and zod validation
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      email: "",
      password: "",
    },
  });

  // Handle form submission
  const onSubmit = async (values: z.infer<typeof formSchema>) => {
    // Check if turnstile token exists
    if (!turnstileToken) {
      toast.error("Please complete the captcha");
      return;
    }

    setIsLoading(true);

    try {
      const { employee, error } = await loginEmployee({
        email: values.email,
        password: values.password,
        turnstileToken,
      });

      if (error) {
        toast.error(error);
      } else {
        setCookie("ykemptoken", employee, {
          maxAge: 60 * 60 * 24 * 7,
        });

        toast.success("Welcome back! Logged in successfully.");
        router.push("/employee/dashboard");
      }
    } catch (err) {
      toast.error("An unexpected error occurred");
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
      <div className="w-full max-w-sm md:max-w-3xl">
        <div className="flex flex-col gap-6">
          <Card className="overflow-hidden shadow-lg">
            <CardContent className="grid p-0 md:grid-cols-2">
              <div className="p-6 md:p-8">
                <div className="mb-6 flex flex-col items-center text-center">
                  <h1 className="text-2xl font-bold">Welcome back</h1>
                  <p className="text-balance text-muted-foreground">
                    Login to your EffenAI Employee Account
                  </p>
                </div>

                <Form {...form}>
                  <form
                    onSubmit={form.handleSubmit(onSubmit)}
                    className="space-y-6"
                  >
                    <FormField
                      control={form.control}
                      name="email"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Email</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="Enter your email"
                              type="email"
                              {...field}
                              disabled={isLoading}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={form.control}
                      name="password"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Password</FormLabel>
                          <FormControl>
                            <Input
                              placeholder="Enter your password"
                              type="password"
                              {...field}
                              disabled={isLoading}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <div className="py-2">
                      <Turnstile
                        siteKey={
                          process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ||
                          "1x00000000000000000000AA"
                        }
                        onVerify={(token) => setTurnstileToken(token)}
                        disabled={isLoading}
                      />
                    </div>

                    <Button
                      type="submit"
                      className="w-full"
                      disabled={!turnstileToken || isLoading}
                    >
                      {isLoading ? "Logging in..." : "Login"}
                    </Button>
                  </form>
                </Form>
              </div>
              <div className="relative hidden bg-white md:block">
                <Image
                  src="/logo-square.png"
                  alt="EffenAI Logo"
                  className="absolute inset-0 h-full w-full object-cover transition-all duration-200 dark:brightness-[0.3] dark:grayscale-[30%]"
                  width={800}
                  height={800}
                  priority
                />
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
};

export default Page;
