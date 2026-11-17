import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const api=createClient<paths>();

export class ApiError extends Error{
    status: number;

    constructor (status:number,message:string){
        super(message);
        this.status=status;
    }
}

function describe(error: unknown): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    return typeof detail === "string" ? detail : JSON.stringify(detail);
  }
  return typeof error === "string" ? error : "Request failed";
}

export function unwrap<T>(result:{
    data?:T;
    error?:unknown;
    response:Response;
}):T{
    if(result.error!=undefined){
        throw new ApiError(result.response.status, describe(result.error));
    }
    return result.data as T
}