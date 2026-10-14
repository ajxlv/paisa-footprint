import { api } from '../lib/api';
import { useApi } from '../lib/useApi';
import { CompaniesTable } from '../components/CompaniesTable';
import { EmissionsChart } from '../components/EmissionsChart';
import { ErrorBox, Loading, PageHeader } from '../components/ui';

export function Companies() {
  const { data, error, loading } = useApi(api.companies);
  return (
    <div>
      <PageHeader title="Companies">
        Scope 1 and Scope 2 emissions parsed from each company's latest BRSR filing, after validation. Click a company
        to see where every number comes from.
      </PageHeader>
      {loading && <Loading />}
      {error && <ErrorBox error={error} />}
      {data && (
        <div className="space-y-10">
          <CompaniesTable companies={data} />
          <EmissionsChart companies={data} />
        </div>
      )}
    </div>
  );
}
