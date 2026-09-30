import { useCallback, useEffect, useMemo, useState } from "react";

export const appRoutes = {
  clientModels: "/client/models",
  clientDocuments: "/client/documents",
  clientDetail: (documentName, model) =>
    `/client/documents/${encodeURIComponent(documentName)}/models/${encodeURIComponent(model)}`,
  advancedExecutive: "/advanced/executive",
  advancedModels: "/advanced/models",
  advancedDocuments: "/advanced/documents",
};

const NAVIGATION_EVENT = "redactbench:navigation";

function safeDecode(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function parseAppRoute(pathname) {
  const path = pathname.replace(/\/+$/, "") || "/";

  if (path === "/" || path === "/client" || path === "/client/models") {
    return {
      area: "client",
      page: "models",
      params: {},
      canonicalPath: appRoutes.clientModels,
    };
  }

  if (path === "/client/documents") {
    return {
      area: "client",
      page: "documents",
      params: {},
      canonicalPath: appRoutes.clientDocuments,
    };
  }

  const detailMatch = path.match(
    /^\/client\/documents\/([^/]+)\/models\/([^/]+)$/,
  );
  if (detailMatch) {
    const documentName = safeDecode(detailMatch[1]);
    const model = safeDecode(detailMatch[2]);
    return {
      area: "client",
      page: "detail",
      params: { documentName, model },
      canonicalPath: appRoutes.clientDetail(documentName, model),
    };
  }

  if (path === "/advanced" || path === "/advanced/executive") {
    return {
      area: "advanced",
      page: "executive",
      params: {},
      canonicalPath: appRoutes.advancedExecutive,
    };
  }

  if (path === "/advanced/models") {
    return {
      area: "advanced",
      page: "models",
      params: {},
      canonicalPath: appRoutes.advancedModels,
    };
  }

  if (path === "/advanced/documents") {
    return {
      area: "advanced",
      page: "documents",
      params: {},
      canonicalPath: appRoutes.advancedDocuments,
    };
  }

  return {
    area: "client",
    page: "models",
    params: {},
    canonicalPath: appRoutes.clientModels,
    notFound: true,
  };
}

function readLocation() {
  const parsed = parseAppRoute(window.location.pathname);
  return {
    ...parsed,
    pathname: window.location.pathname,
    search: window.location.search,
    searchParams: new URLSearchParams(window.location.search),
  };
}

function emitNavigation() {
  window.dispatchEvent(new Event(NAVIGATION_EVENT));
}

export function useAppRoute() {
  const [locationState, setLocationState] = useState(readLocation);

  useEffect(() => {
    const sync = () => setLocationState(readLocation());
    window.addEventListener("popstate", sync);
    window.addEventListener(NAVIGATION_EVENT, sync);
    return () => {
      window.removeEventListener("popstate", sync);
      window.removeEventListener(NAVIGATION_EVENT, sync);
    };
  }, []);

  useEffect(() => {
    if (
      locationState.notFound ||
      locationState.pathname !== locationState.canonicalPath
    ) {
      const next = `${locationState.canonicalPath}${locationState.search}`;
      window.history.replaceState({}, "", next);
      emitNavigation();
    }
  }, [
    locationState.canonicalPath,
    locationState.notFound,
    locationState.pathname,
    locationState.search,
  ]);

  const navigate = useCallback(
    (
      pathname,
      {
        replace = false,
        preserveSearch = true,
        searchParams = null,
      } = {},
    ) => {
      let search = preserveSearch ? window.location.search : "";
      if (searchParams) {
        const encoded = searchParams.toString();
        search = encoded ? `?${encoded}` : "";
      }
      const next = `${pathname}${search}`;
      if (replace) {
        window.history.replaceState({}, "", next);
      } else {
        window.history.pushState({}, "", next);
      }
      emitNavigation();
      window.scrollTo({ top: 0, behavior: "auto" });
    },
    [],
  );

  const setQueryParam = useCallback(
    (name, value, { replace = false } = {}) => {
      const searchParams = new URLSearchParams(window.location.search);
      if (value === null || value === undefined || value === "") {
        searchParams.delete(name);
      } else {
        searchParams.set(name, value);
      }
      navigate(window.location.pathname, {
        replace,
        preserveSearch: false,
        searchParams,
      });
    },
    [navigate],
  );

  return useMemo(
    () => ({
      ...locationState,
      navigate,
      setQueryParam,
    }),
    [locationState, navigate, setQueryParam],
  );
}
